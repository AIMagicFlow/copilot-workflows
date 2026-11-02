# Document Sanitizer: guía rápida para TI

Escrita para: administradores de TI con permisos para crear recursos en la suscripción de Azure del cliente.

Document Sanitizer es una Azure Function que convierte un documento subido en texto plano o Markdown y redacta los datos sensibles antes de que el texto llegue a SharePoint. Se ejecuta en **su** suscripción y región de Azure. Los documentos no salen de su tenant.

## Lo que necesita

- Una suscripción de Azure donde pueda crear grupos de recursos y asignaciones de roles. Crear asignaciones de roles requiere el rol Propietario, o Administrador de acceso de usuarios, en el grupo de recursos.
- La CLI de Azure, una versión actual, con las herramientas de Bicep (`az bicep install`).
- PowerShell 7.4 o posterior.
- La carpeta de la versión que le han entregado. Contiene `deploy.ps1`, `azuredeploy.json`, el zip y `SHA256SUMS`.
- Una región elegida según su política de datos. Todos los recursos se crean en esa región.

## 1. Compruebe la versión

```powershell
cd <carpeta de la versión>
Get-FileHash -Algorithm SHA256 *.zip, azuredeploy.json, deploy.ps1
```

Compare cada hash con la línea correspondiente de `SHA256SUMS`. No despliegue si alguno no coincide.

## 2. Despliegue

```powershell
az login
./deploy.ps1 -ResourceGroup rg-sanitizer -Location westeurope -NamePrefix dsanit01
```

El script crea el grupo de recursos, despliega la infraestructura (Function App, almacenamiento, Application Insights, Document Intelligence y una identidad administrada con los roles que necesita) y despliega el código de la función. Al terminar muestra el nombre del host.

Use un prefijo de 3 a 12 letras minúsculas o dígitos. Aparece en el nombre de todos los recursos.

## 3. Obtenga la clave de la función

La clave es la única credencial que usan los flujos. El script nunca la muestra.

1. Abra la Function App en el portal de Azure.
2. Vaya a **Functions > sanitize_document > Function Keys**.
3. Copie la clave **default**.

Entregue la clave a la persona que crea la conexión de Power Platform. No la pegue en un correo, en un chat, en un ticket ni en la solución.

## 4. Configure Power Platform

Estos pasos siguen la guía rápida de cada vertical. El vertical define las variables de entorno y la referencia de conexión.

1. Asigne a la variable de entorno del host del sanitizador (`<prefijo>_SanitizerHost`) el valor `https://<nombre del host del paso 2>`. Déjela vacía para mantener el complemento desactivado.
2. Asigne a la variable de entorno del perfil (`<prefijo>_SanitizerProfile`) el valor `default-pii`.
3. Cree la conexión del sanitizador con la clave de función del paso 3.
4. Active el flujo.

## Qué hace el servicio

- Los archivos de texto (TXT, CSV, MD, JSON, XML, LOG) se decodifican directamente.
- El HTML se limpia de scripts, estilos, comentarios y elementos ocultos, y después se convierte.
- Los PDF, Word, Excel, PowerPoint y las imágenes pasan por Azure AI Document Intelligence `prebuilt-read`, que incluye OCR.
- Redacción, en este orden: los términos literales indicados por el llamante (sin distinguir mayúsculas, palabras completas), después las direcciones de correo y, por último, los teléfonos.
- La respuesta contiene el texto sanitizado y los recuentos. Nunca contiene los valores encontrados.
- Se rechazan los archivos de Office antiguos (DOC, XLS, PPT), los archivos con macros y los cifrados.

## Límites

| Límite | Valor por defecto | Ajuste |
|---|---|---|
| Tamaño de archivo | 10 MB | `SANITIZER_MAX_FILE_BYTES` |
| Texto extraído | 5 MB | `SANITIZER_MAX_TEXT_BYTES` |
| Páginas de PDF, síncrono | 100 | `SANITIZER_MAX_SYNC_PAGES` |
| Términos del llamante | 500, 200 caracteres cada uno | fijo |
| Espera de Document Intelligence | 90 s | `SANITIZER_DI_TIMEOUT_SECONDS` |

## Códigos de error

Todo cuerpo de error es `{"status": "failed", "error": {"code", "message"}, "correlationId"}`.

| HTTP | Código | Significado | ¿Reintenta el flujo? |
|---|---|---|---|
| 400 | `INVALID_REQUEST`, `INVALID_BASE64` | Solicitud mal formada, o Base64 no válido | no |
| 401 | (host) | Falta la clave de función | no |
| 403 | (host) | La clave de función no es válida | no |
| 413 | `FILE_TOO_LARGE`, `TEXT_TOO_LARGE`, `PAGE_LIMIT_EXCEEDED` | Supera un límite | no |
| 415 | `UNSUPPORTED_TYPE` | Tipo no admitido | no |
| 422 | `NOT_EXTRACTABLE`, `REDACTION_INCOMPLETE` | Sin texto, cifrado, dañado, o falló la comprobación de redacción | no |
| 429 | `THROTTLED` | Limitado por cuota; respete `Retry-After` | sí |
| 500 | `INTERNAL` | Error inesperado | no |
| 502 | `DEPENDENCY_ERROR` | Document Intelligence falló | sí |
| 503 | `DEPENDENCY_UNAVAILABLE` | Document Intelligence no está disponible | sí |
| 504 | `DEPENDENCY_TIMEOUT` | Document Intelligence no terminó a tiempo | sí |

Ante cualquier error el flujo falla en modo seguro: el elemento de origen se registra solo con metadatos y ningún contenido llega a SharePoint.

## Registros

Application Insights guarda solo metadatos: identificador de correlación, tipo detectado, tamaño en bytes, duración, extractor, estado, recuentos y código de error. Nunca guarda texto de documentos, nombres de archivo ni valores encontrados.

## Lista de verificación de aceptación manual

Estas comprobaciones necesitan un tenant real de Azure. No se ejecutaron en la compilación del repositorio. Ejecute cada una antes de la primera entrega al cliente y registre el resultado.

- [ ] `az bicep build` termina sin errores sobre `infra/main.bicep` con la versión de Bicep en uso. (CI lo ejecuta en cada cambio.)
- [ ] `deploy.ps1` despliega en un grupo de recursos vacío de la región del cliente.
- [ ] El zip se despliega con compilación remota, que instala `requirements.txt` en Flex Consumption.
- [ ] Los GUID de definición de rol de `infra/main.bicep` son roles integrados: Storage Blob Data Owner, Storage Queue Data Contributor, Storage Table Data Contributor, Cognitive Services User. Compruebe cada uno en la referencia de roles integrados de Azure.
- [ ] La identidad puede llamar a Document Intelligence con `disableLocalAuth` activado. Una solicitud con la clave de función devuelve 200 para un PDF digital.
- [ ] La salida de `prebuilt-read` de Document Intelligence para un PDF digital, un PDF escaneado, DOCX, XLSX, PPTX y un JPEG tiene la forma que lee el código (`content`, `pages`). La versión de la API fijada en `requirements.txt` acepta `output_content_format`.
- [ ] Un archivo cifrado y uno dañado devuelven 422 `NOT_EXTRACTABLE`. Confirme el estado HTTP que devuelve el servicio en cada caso.
- [ ] Una solicitud sin `x-functions-key` devuelve 401. Una con una clave incorrecta devuelve 403.
- [ ] Una solicitud síncrona de un archivo de 10 MB termina en menos de 100 s.
- [ ] Application Insights no contiene cuerpos de solicitud ni texto de documentos tras una prueba.
- [ ] El marcador del host del conector personalizado se sustituye por entorno, y el conector acepta la clave en un entorno en español (ADR-001).
- [ ] La cadena de conexión de Application Insights es el único valor de telemetría guardado en la configuración. Confirme que la política del cliente lo acepta.

## Soporte

Envíe el identificador de correlación del cuerpo del error, la hora de la solicitud y el código de error. Nunca envíe contenido de documentos ni la clave de función.
