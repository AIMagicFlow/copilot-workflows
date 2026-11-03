# Vigilante de Tendencias: guía de inicio rápido

Esta guía instala el Vigilante de Tendencias en su tenant de Microsoft 365 en unos 45 minutos. Al terminar tendrá seis flujos automáticos:

| Flujo | Cuándo se ejecuta (UTC) | Qué hace |
|---|---|---|
| **VT Recolectar RSS** | Todos los días, 11:00 | Lee las fuentes RSS habilitadas y guarda cada artículo nuevo como evidencia. |
| **VT Clasificar Elementos** | Todos los días, 16:00 | Evalúa cada artículo nuevo frente a cada brief habilitado y crea una señal. |
| **VT Resumen Semanal** | Lunes, 08:00 | Publica un resumen HTML por brief, agrupado por objetivo, y le avisa por Teams. |
| **VT Procesar Documentos** | Cada 5 minutos | Lee como evidencia los archivos de texto cargados en `SourceUploads/PublicData` (paso 5). |
| **VT Caso de Negocio** | Cada 5 minutos | Genera un borrador de caso de negocio a partir de resúmenes elegidos, lo envía a aprobación y luego lo publica (paso 6). |
| **VT Limpiar Señales** | Mensual (día 1), 03:00 | Elimina las señales `Rejected` y `Monitor` antiguas y sus archivos de evidencia (paso 5). |

## Qué necesita

- Dos archivos de la versión publicada (carpeta `releases/trend-researcher/<versión>/`):
  - `TrendResearcher_<versión>_es.zip`: la solución de Power Platform. **No lo descomprima.**
  - `TrendResearcher_<versión>_es_sharepoint.zip`: el kit de SharePoint. **Descomprímalo.**
- Un entorno de Power Platform con Dataverse y licencia de Copilot Studio (flujos de agente).
- Si el idioma base del entorno no es español, el paquete de idioma español habilitado en el entorno.
- Permiso para crear sitios de SharePoint, o un sitio ya creado del que sea propietario.

## 1. Cree el sitio de SharePoint

1. En SharePoint, seleccione **Crear sitio → Sitio de grupo**. Use un nombre como `Vigilante de Tendencias` y privacidad **Privado**.
2. Copie la URL del sitio, por ejemplo `https://contoso.sharepoint.com/sites/VigilanteTendencias`. La necesitará en los pasos 2 y 3.

## 2. Cree las listas y bibliotecas (elija una opción)

Los flujos dependen del **nombre interno** de cada columna (por ejemplo `field_3`), no del nombre visible. Las dos opciones crean las mismas seis listas (`Briefs`, `Fuentes`, `ElementosFuente`, `Señales`, `Publicaciones`, `SolicitudesCasoNegocio`) y las cuatro bibliotecas (`Evidence`, `PublishedReports`, `ResearchDrafts`, `SourceUploads`).

| | Opción A: archivos CSV | Opción B: PnP PowerShell |
|---|---|---|
| Para quién | Cualquier propietario del sitio | Equipo de TI con PowerShell |
| Herramientas | Solo el navegador | PowerShell 7.4+, módulo PnP.PowerShell y una app de Entra ID |
| Nombres internos | Dependen de cómo SharePoint importe el CSV: hay que verificarlos | **Garantizados** por la plantilla y verificados automáticamente |
| Bibliotecas | Se crean a mano | Se crean solas |
| Actualizaciones futuras | Agregar columnas a mano | Volver a ejecutar el script |

### Opción A: archivos CSV

**Bibliotecas.** Los flujos escriben en las rutas `/Evidence`, `/PublishedReports` y `/ResearchDrafts`, y `VT Procesar Documentos` vigila `/SourceUploads`. Cree cada biblioteca **con el nombre en inglés** (ese nombre define la URL) y después cámbiele el nombre visible (en la tabla siguiente).

**Carpeta de cargas.** Abra la biblioteca `SourceUploads` y cree una carpeta llamada exactamente `PublicData`. El flujo solo lee los archivos que están debajo de ella. (La opción B la crea por usted.)

| Crear con el nombre | Después renombrar a |
|---|---|
| `Evidence` | Evidencias |
| `PublishedReports` | Informes publicados |
| `ResearchDrafts` | Borradores de investigación |
| `SourceUploads` | Cargas de fuentes |

Para cada una: **Nuevo → Biblioteca de documentos → En blanco**, escriba el nombre en inglés y seleccione **Crear**. Para cambiar el nombre visible: **Configuración → Configuración de la biblioteca → Nombre, descripción y navegación**.

**Listas.** En la carpeta `lists/` del kit hay un archivo por lista. Cada archivo contiene el esquema completo, incluidos los nombres internos. Para cada archivo:

1. En el sitio, seleccione **Nuevo → Lista → Desde CSV**.
2. Cargue el archivo. Deje el nombre de la lista **igual al nombre del archivo** (por ejemplo, `Fuentes`).
3. Revise que los tipos de columna propuestos coincidan con el esquema y seleccione **Crear**.

`Fuentes` y `Briefs` incluyen filas de ejemplo: nueve feeds RSS públicos y un brief sobre IA de voz. Edítelas o elimínelas en el paso 5. El brief de ejemplo no tiene *Producto* ni *Dimensión*: ambos son obligatorios, así que complételos antes de habilitarlo.

`SolicitudesCasoNegocio` es la lista con la que los analistas piden un caso de negocio (paso 6). El archivo tiene 17 columnas.

**Verifique los nombres internos (obligatorio).** Si su equipo de TI tiene PnP PowerShell, ejecute `pnp/provision.ps1 ... -VerifyOnly` (vea la opción B): revisa todas las columnas sin cambiar nada. Si no, compruebe una columna por lista a mano:

1. Abra la lista → **Configuración → Configuración de la lista**.
2. Seleccione la columna indicada y mire la URL del navegador. Debe terminar en el valor `Field=` indicado.

| Lista | Columna | La URL debe terminar en |
|---|---|---|
| Fuentes | URL del feed | `Field=field_1` |
| Briefs | Habilitado | `Field=field_7` |
| ElementosFuente | Estado | `Field=field_9` |
| Señales | Estado | `Field=field_11` |
| Publicaciones | Clave de publicación | `Field=field_1` |

Compruebe también que **Clave del elemento** (ElementosFuente), **Clave de análisis** (Señales) y **Clave de publicación** (Publicaciones) tengan activado **Aplicar valores únicos: Sí**. Esa restricción impide duplicados.

Si algún `Field=` es distinto, **no continúe**: los flujos no encontrarán esa columna. Borre esa lista y use la opción B, o avísenos con una captura de la URL.

### Restrinja la biblioteca `ResearchDrafts` (ambas opciones)

Los borradores de casos de negocio esperan aquí su revisión, antes de que nadie los haya aprobado. Ninguna de las dos opciones restringe la biblioteca, así que hágalo una vez:

1. Abra `ResearchDrafts` → **Configuración → Configuración de la biblioteca → Permisos de esta biblioteca de documentos**.
2. Seleccione **Dejar de heredar permisos**.
3. Quite todos los grupos que no necesite y dé acceso solo a quienes piden casos de negocio, a quienes los revisan y a la cuenta de la conexión *Vigilante de Tendencias - SharePoint* (la cuenta del flujo). Sin acceso, el flujo no puede escribir borradores.

El correo de aprobación incluye un enlace al borrador, así que cada revisor debe poder abrirlo.

### Opción B: PnP PowerShell

La carpeta `pnp/` del kit contiene la plantilla (`sharepoint-template.pnp.xml`) y el script `provision.ps1`. El script aplica la plantilla y luego verifica cada lista, biblioteca, columna y restricción de valores únicos. Se puede ejecutar varias veces: conserva lo que ya existe.

**Preparación (una sola vez por tenant):**

1. Instale PowerShell 7.4 o posterior. En Windows: `winget install Microsoft.PowerShell`.
2. En PowerShell 7: `Install-Module PnP.PowerShell -Scope CurrentUser`.
3. Registre una app de Entra ID para PnP. Requiere el rol **Desarrollador de aplicaciones** o **Administrador global**, y otorgar el consentimiento puede requerir un **Administrador global**:

   ```powershell
   Register-PnPEntraIDAppForInteractiveLogin -ApplicationName "PnP.PowerShell" -Tenant <tenant>.onmicrosoft.com
   ```

   Anote el **ID de aplicación (cliente)** que muestra el comando. Si su tenant ya tiene una app para PnP, use esa.

**Ejecución:**

```powershell
cd <carpeta del kit>/pnp
./provision.ps1 -SiteUrl https://contoso.sharepoint.com/sites/VigilanteTendencias -ClientId <ID de aplicación>
```

Inicie sesión cuando se abra el navegador. Al final debe ver **Todas las listas, bibliotecas y columnas coinciden con el esquema esperado.** Si aparece algún punto en rojo, corríjalo y vuelva a ejecutar el script.

Con la opción B las listas quedan en URL estables en inglés (`/Lists/Sources`) con títulos en español (`Fuentes`). Los flujos usan el título.

## 3. Importe la solución

1. Abra [make.powerapps.com](https://make.powerapps.com) y elija el entorno correcto (arriba a la derecha).
2. Vaya a **Soluciones → Importar solución → Examinar**, elija `TrendResearcher_<versión>_es.zip` y seleccione **Siguiente**.
3. **Conexiones.** Para cada referencia de conexión, elija una conexión existente o cree una nueva con la cuenta de servicio acordada:

   | Referencia | Conector | Cuenta |
   |---|---|---|
   | Vigilante de Tendencias - SharePoint | SharePoint | Con lectura y escritura en el sitio del paso 1 |
   | Vigilante de Tendencias - RSS | RSS | No requiere cuenta |
   | Vigilante de Tendencias - Teams | Microsoft Teams | Quien recibirá el aviso del resumen |
   | Vigilante de Tendencias - Clasificador IA | Agente de Copilot Studio | La cuenta con licencia de Copilot Studio |
   | Vigilante de Tendencias - Aprobaciones | Aprobaciones | La cuenta de servicio que envía las aprobaciones de casos de negocio. Es quien envía; el revisor es el *ReviewerEmail* de la solicitud. |

4. **Variables de entorno.**

   | Variable | Valor |
   |---|---|
   | URL del sitio | La URL del paso 1, sin barra final |
   | Lista de briefs / fuentes / elementos fuente / señales / publicaciones | Ya vienen con `Briefs`, `Fuentes`, `ElementosFuente`, `Señales`, `Publicaciones`. Cámbielas solo si usó otros nombres de lista. También acepta el ID (GUID) de la lista. |
   | Límite diario de clasificación | `50` (máximo de elementos clasificados por día). Cada elemento se clasifica una vez por brief habilitado. |
   | Biblioteca de cargas de fuentes | Ya viene con el título de la biblioteca (`Cargas de fuentes`). Si el desencadenador del flujo rechaza el título, escriba el ID (GUID) de la biblioteca. |
   | Tamaño máximo de carga (bytes) | `1000000`. Los archivos más grandes se registran solo por nombre (vea el paso 5). |

   | Lista de solicitudes de caso de negocio | Ya viene con el título de la lista (`SolicitudesCasoNegocio`). **Use el título, no el GUID**: el paso de reserva llama a la API REST de SharePoint por título de lista. |
   | Revisores aprobados (`tr_ApprovedReviewers`) | Obligatoria. Los correos permitidos como *ReviewerEmail*, separados por punto y coma, por ejemplo `ana@contoso.com;luis@contoso.com`. Si está vacía, se rechaza toda solicitud. |
   | Audiencias aprobadas (`tr_ApprovedAudiences`) | Obligatoria. Los valores permitidos como *AudienceKey*, separados por punto y coma, por ejemplo `Direccion;Producto`. Si está vacía, se rechaza toda solicitud. |
   | Audiencia de notificación (`tr_NotificationAudience`) | Opcional. El canal de Teams que recibe los casos de negocio aprobados, escrito `teamId|channelId`. Si está vacía, el mensaje va al propietario del flujo. |
   | Entrada máxima del caso de negocio (caracteres) | `60000` (valor por defecto). El máximo de texto de resúmenes que una solicitud puede enviar a la IA. Una solicitud mayor pasa a `Failed` antes de llamar a la IA. |

   El resto de variables están reservadas para versiones futuras. Déjelas vacías.

5. Seleccione **Importar** y espere el mensaje de éxito (1 o 2 minutos).

## 4. Active los flujos

1. En **Soluciones**, abra **Vigilante de Tendencias → Flujos de nube**.
2. Compruebe que **VT Recolectar RSS**, **VT Clasificar Elementos**, **VT Resumen Semanal**, **VT Procesar Documentos**, **VT Caso de Negocio** y **VT Limpiar Señales** están **Activados**. Si alguno aparece desactivado, selecciónelo y elija **Activar**.

Los mismos flujos aparecen en Copilot Studio en **Flujos**.

## 5. Configure su investigación

- **Briefs**: edite el brief de ejemplo o cree uno nuevo. Complete *Pregunta*, *Palabras clave*, *Exclusiones*, *Idiomas* y *Geografías*, y los tres campos nuevos de 1.3:
  - *Producto* (obligatorio): el producto del que trata el brief. El encabezado del resumen lo muestra, y un caso de negocio solo acepta resúmenes cuyo Producto coincida con el de la solicitud.
  - *Dimensión* (obligatoria): `Market`, `Technology`, `Regulatory` o `Competition`. **Estos cuatro códigos son provisionales.** La lista final aún no está acordada y puede cambiar.
  - *Tipo de brief*: `Monitoring` (por defecto) o `Investigation`.

  Use `1` en *Habilitado* para activarlo y `0` para desactivarlo. Si cambia la pregunta de un brief existente, aumente *Versión del brief*: los elementos nuevos se analizarán con la versión nueva.
- **Fuentes**: deje solo los feeds RSS aprobados. Use `1` en *Habilitada* para recolectar de una fuente y `0` para pausarla. Use `RSS` en *Tipo de fuente*.
- **Documentos cargados (opcional).** Agregue una fila en **Fuentes** por cada subcarpeta de cargas:
  1. En `SourceUploads/PublicData`, cree una subcarpeta para la fuente, por ejemplo `VendorDocuments`.
  2. En **Fuentes**, agregue una fila con *Título* (el nombre de la fuente), *Tipo de fuente* `Upload`, *Ruta de la fuente* `/SourceUploads/PublicData/VendorDocuments` (nombre de URL de la biblioteca más la ruta de la carpeta, sin barra final) y *Habilitada* `1`.
  3. Cargue los archivos en esa subcarpeta. `VT Procesar Documentos` busca archivos nuevos o modificados cada 5 minutos.

  Qué hace el flujo con una carga:
  - **Los archivos de texto se leen.** `.txt`, `.md`, `.csv`, `.html` y `.htm` (con cualquier combinación de mayúsculas) se leen como texto UTF-8. El HTML se conserva tal cual, con sus etiquetas.
  - **Todo lo demás se registra solo por nombre.** PDF, Word, Excel, PowerPoint y cualquier otro tipo generan un ElementoFuente con *ContentStatus* `MetadataOnly`: el clasificador ve el nombre del archivo y la carpeta, no el contenido.
  - **Límite de tamaño.** Un archivo de texto mayor que *Tamaño máximo de carga* (por defecto 1.000.000 de bytes) también queda como `MetadataOnly`.
  - **Solo se leen las subcarpetas de `PublicData`.** Un archivo puesto directamente en `PublicData`, o en cualquier otra carpeta, se ignora. Cada subcarpeta necesita su propia fila `Upload` habilitada en Fuentes, o sus archivos se ignoran.
  - **No cargue documentos privados.** Esta versión no tiene redacción. Vea [ADR-001](design/adr-001-text-only-uploads.md).
  - **Sin duplicados.** Volver a cargar el mismo archivo, editarlo o renombrarlo no crea un segundo elemento. El flujo identifica el archivo por su ID de elemento de SharePoint.
  - Cada archivo procesado agrega un archivo de texto en **Evidencias** llamado `upload-<ID del elemento>.txt` y un ElementoFuente con *Estado* `Ready`. La siguiente ejecución de **VT Clasificar Elementos** lo clasifica.

  Límites conocidos, aún no verificados en un tenant: el flujo supone que la ruta del archivo que recibe empieza con `/SourceUploads/`; una carpeta creada en la biblioteca también puede generar un elemento `MetadataOnly`; y el vínculo al archivo guardado en el ElementoFuente está limitado a 255 caracteres.
- **Vistas por etiqueta en Señales (opcional, recomendado).** Cada señal tiene *Etiquetas de alerta* (`CompetitorLaunch`, `RegulatoryAlert`, `NewTechnology`) y *Objetivos estratégicos* (`Anticipate`, `MinimizeRisks`, `Compare`, `Innovate`, `Cooperate`). Cree una vista por etiqueta de alerta para que los analistas las revisen:
  1. Abra **Señales** → **Todos los elementos → Guardar vista como** (o **Crear vista**) y póngale el nombre de la etiqueta, por ejemplo `CompetitorLaunch`.
  2. Filtro: *Etiquetas de alerta* **contiene** esa etiqueta.
  3. Repita con las otras dos etiquetas. Una señal con varias etiquetas aparece en cada vista.

  Una etiqueta sirve para revisar, no es una notificación: al etiquetar una señal no se envía nada. Si el modelo devuelve una etiqueta fuera de los tres códigos permitidos, la señal se guarda sin la etiqueta inválida, su *Estado* queda en `NeedsReview` y las etiquetas inválidas se escriben en *Notas de evidencia*. Revise esas señales a mano.
- **Limpieza por retención.** El día 1 de cada mes, **VT Limpiar Señales** elimina las señales `Rejected` y `Monitor` más antiguas que *tr_RetentionDays* (por defecto 90; `0` desactiva la limpieza). Las señales `Digest` y `NeedsReview` se conservan a cualquier antigüedad. Cuando una señal eliminada era la última de su elemento de fuente, el flujo también elimina el archivo de evidencia de ese elemento y marca el ElementoFuente con *ContentStatus* `Purged` y *EvidenceUrl* vacío. La fila se conserva, así que el elemento no se vuelve a recolectar. Los originales cargados, las publicaciones y los borradores de caso de negocio nunca se tocan.
- **Formato del resumen.** El resumen semanal muestra en el encabezado el producto, la dimensión y la pregunta del brief, y agrupa las señales bajo un título por objetivo, en este orden: Anticipar, Minimizar riesgos, Comparar, Innovar, Cooperar. Una señal con varios objetivos aparece bajo cada uno; un objetivo sin señales lo indica.

## 6. Solicite y apruebe un caso de negocio

Un caso de negocio es un informe orientado a una decisión, construido a partir de uno a cinco resúmenes existentes del mismo producto. Los analistas lo piden en la lista **SolicitudesCasoNegocio** (en inglés: `BusinessCaseRequests`).

**Antes de la primera solicitud**, compruebe que:
- `ResearchDrafts` está restringida (paso 2) y el revisor puede abrirla.
- *Revisores aprobados* y *Audiencias aprobadas* están configuradas (paso 3). Una solicitud cuyo *ReviewerEmail* o *AudienceKey* no esté en esas listas no se procesa, y su *Estado* sigue en `Submitted`.
- Los resúmenes existen y son elegibles (vea más abajo).

**Envíe una solicitud.**
1. En **SolicitudesCasoNegocio**, agregue un elemento y complete las columnas obligatorias: *Título*, *Producto*, *Pregunta de decisión*, *Geografías*, *Horizonte temporal*, *Alternativas*, *Objetivos estratégicos*, *IDs de publicaciones de entrada*, *Correo del revisor*, *Clave de audiencia* y *Versión* (empieza en 1).
2. *IDs de publicaciones de entrada* es una lista separada por comas de 1 a 5 IDs distintos de Publicaciones, por ejemplo `12,15,19`. Cada uno debe ser un **resumen** (no un caso de negocio) cuyo *Producto* sea igual al *Producto* de la solicitud y que tenga archivo de informe.
3. *Datos financieros* y *Restricciones* son opcionales. Si deja vacío *Datos financieros*, el informe indica que costos y ROI son `Unknown`. El flujo nunca calcula el ROI sin valores aportados.
4. Cambie *Estado* a `Submitted`. El flujo arranca en su siguiente consulta, en un máximo de 5 minutos.

**Qué ocurre después.**
1. El flujo reserva la solicitud (*Estado* `Generating`), lee los resúmenes, pide el caso a la IA y comprueba que cada cita apunte a uno de los resúmenes de entrada.
2. Guarda un borrador HTML en `ResearchDrafts` (`businesscase-<ID de la solicitud>-v<Versión>.html`) y una fila en Publicaciones con *Estado de revisión* `Draft`.
3. Envía una aprobación al *Correo del revisor* de la solicitud (*Estado* `InReview`). El revisor tiene **14 días** para responder.
4. **Aprobado:** el borrador se copia a `PublishedReports`, el *Estado* pasa a `Approved` y el enlace se publica en el canal de Teams de *Audiencia de notificación*. Si esa variable está vacía, el mensaje va al propietario del flujo.
5. **Rechazado o sin respuesta en 14 días:** el *Estado* pasa a `Rejected`. El borrador queda en `ResearchDrafts` y no se publica.

**Regla para el revisor (vigente).** No edite el borrador después de que se solicite la aprobación. Si el archivo cambia después, se bloquea la publicación y la solicitud pasa a `Failed`. Para cambiar algo, rechace la solicitud y vuelva a enviarla. Esta es la regla actual y el cliente puede cambiarla.

**Solicitudes fallidas y reintentos.** En una solicitud fallida, *Último error* indica el motivo (solo el paso que falló y el código de estado, nunca contenido de documentos).
- **Falló antes de crearse una Publicación** (por ejemplo, datos no válidos o un resumen no elegible): corrija la causa y vuelva a poner *Estado* en `Submitted`, con la misma *Versión*.
- **Ya tiene una Publicación** (se creó el borrador y luego algo falló, se rechazó o venció el plazo): primero **aumente la *Versión***, y después ponga *Estado* en `Submitted`. Si deja la misma *Versión*, el flujo encuentra la Publicación existente y se detiene sin hacer nada.
- **Se quedó en `Generating`** (por ejemplo, se canceló la ejecución del flujo): aplique la misma regla. Vuelva a poner *Estado* en `Submitted`, aumentando antes la *Versión* si ya existe una Publicación de esa versión.

**Los resúmenes creados antes de 1.3 deben completarse** antes de que un caso de negocio pueda usarlos. En **Publicaciones**, para cada resumen antiguo que quiera usar, ponga *Tipo de publicación* en `Digest` y *Producto* con el producto de su brief (el mismo texto que el *Producto* de la solicitud). El flujo elige un resumen por *Tipo de publicación* `Digest`, un *Producto* coincidente y un archivo de informe no vacío; los resúmenes de 1.2 ya tienen el archivo de informe. Los resúmenes creados después de actualizar se completan solos.

**Límites.**
- Una aprobación pendiente ocupa una de las 25 plazas de ejecución simultánea del flujo, así que como máximo 25 solicitudes pueden esperar aprobación a la vez.
- Una edición hecha en los pocos segundos entre la comprobación del borrador y la copia a `PublishedReports` aún podría publicarse. Es un riesgo conocido.

## 7. Pruebe de punta a punta

Ejecute cada flujo una vez con **Probar → Manualmente**, en este orden:

1. **VT Recolectar RSS** → aparecen filas en **ElementosFuente** con *Estado* `Ready` y archivos `.txt` en **Evidencias**.
2. **VT Clasificar Elementos** → aparecen filas en **Señales**. Los elementos procesados cambian a `Classified`.
3. **VT Resumen Semanal** → aparece un archivo HTML en **Informes publicados** y una fila en **Publicaciones**, y recibe un mensaje en Teams. Si ninguna señal llegó a relevancia 70 o más en los últimos 7 días, no se genera resumen. Es el comportamiento esperado.
4. **VT Procesar Documentos** (si agregó una fuente `Upload`) se ejecuta sola cuando se agrega un archivo. Cargue un `.txt` pequeño en la subcarpeta de la fuente y espere unos 5 minutos. Aparecen un ElementoFuente con *ContentStatus* `FullText` y un archivo en **Evidencias**.
5. **VT Caso de Negocio** (opcional) se ejecuta sola ante una solicitud enviada. Envíe una solicitud como en el paso 6 y espere hasta 5 minutos. Aparece un borrador en `ResearchDrafts` y el revisor recibe una aprobación.

Las columnas de estado (*Estado*, *Impacto*, *Horizonte*) guardan códigos en inglés (`Ready`, `Digest`, `High`…) a propósito: los flujos filtran por esos valores. El resumen HTML los muestra traducidos.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `List not found` o `Lista no encontrada` | El nombre de la lista no coincide con la variable de entorno. Corrija la variable (o use el GUID de la lista) y luego **desactive y active** el flujo. |
| `Column 'field_N' does not exist` | La columna no tiene el nombre interno esperado. Ejecute `provision.ps1 -VerifyOnly` o revise el paso 2. |
| Cambié una variable de entorno y el flujo sigue usando el valor anterior | Desactive y vuelva a activar el flujo. El cambio puede tardar hasta una hora en propagarse. |
| `Input exceeds the maximum length of 255` | Una columna de texto largo se creó como texto de una línea. Ejecute `provision.ps1 -VerifyOnly` para encontrarla. |
| Una solicitud de caso de negocio sigue en `Submitted` y no pasa nada | La solicitud no superó la validación y el flujo la dejó sin cambios. Compruebe que todas las columnas obligatorias estén completas, que *Versión* sea un entero de 1 o más y que *Correo del revisor* y *Clave de audiencia* estén en las listas aprobadas. El historial de ejecuciones del flujo muestra el motivo. |
| Una solicitud de caso de negocio está en `Failed` | Lea *Último error* y siga la regla de reintento del paso 6 (aumente antes la *Versión* si ya existe una Publicación). |

## Actualizar a una versión nueva

Importe el zip nuevo con **Soluciones → Importar solución**, igual que en el paso 3. La solución se actualiza en su lugar. Sus listas, datos y valores de variables de entorno se conservan. Si usó la opción B, vuelva a ejecutar `provision.ps1` del kit nuevo: agrega las columnas nuevas. Con la opción A, agréguelas a mano según las notas de la versión.

### Actualizar de 1.1 a 1.2

1.2.0.0 agrega el flujo `VT Procesar Documentos`, la biblioteca `SourceUploads` y la columna `SourcePath` en **Fuentes**. Siga el archivo `upgrade-1.2.0.0.es.md` que genera la compilación, dentro del zip del kit de SharePoint: indica qué agregar a mano si usó la opción A. Después:

1. Cree la biblioteca `SourceUploads` y su carpeta `PublicData` (la opción B lo hace al ejecutar `provision.ps1`).
2. Importe la solución nueva. Pedirá las dos variables de entorno nuevas, *Biblioteca de cargas de fuentes* y *Tamaño máximo de carga*.
3. Active **VT Procesar Documentos** y agregue filas `Upload` en **Fuentes** (paso 5).
4. Lea la entrada 1.2.0.0 de `CHANGELOG.md` antes de actualizar. Describe la corrección del ItemKey en `VT Recolectar RSS`; su efecto sobre los elementos existentes está pendiente de verificación en el tenant de desarrollo.

### Actualizar de 1.2 a 1.3

1.3.0.0 agrega la lista **SolicitudesCasoNegocio**, el flujo `VT Caso de Negocio` y columnas nuevas en **Briefs**, **Señales** y **Publicaciones**. También cambia el prompt del clasificador y el formato del resumen. Siga el archivo `upgrade-1.3.0.0.es.md` que genera la compilación, dentro del zip del kit de SharePoint: indica qué agregar a mano si usó la opción A. Después:

1. Agregue las columnas nuevas y cree la lista `SolicitudesCasoNegocio` (la opción B lo hace al ejecutar `provision.ps1`).
2. Restrinja la biblioteca `ResearchDrafts` (paso 2).
3. Complete *Producto* y *Dimensión* en todos los briefs existentes. Son obligatorios y el prompt del clasificador (ahora versión 3) los lee. La versión del prompt forma parte de la clave de cada señal, así que las señales escritas con la versión 3 son filas nuevas.
4. Importe la solución nueva. Pedirá una conexión nueva de **Aprobaciones** y las variables de entorno nuevas (paso 3): configure *Revisores aprobados* y *Audiencias aprobadas*, y opcionalmente *Audiencia de notificación*.
5. Active **VT Caso de Negocio**.
6. Complete *Tipo de publicación* y *Producto* en los resúmenes antiguos que quiera usar (paso 6).
7. Cree las vistas por etiqueta en **Señales** (paso 5).

Lea la entrada 1.3.0.0 de `CHANGELOG.md` antes de actualizar.

### Actualizar de 1.3 a 1.4

1.4.0.0 agrega el flujo **VT Limpiar Señales** y la variable `tr_RetentionDays`. También indexa dos columnas en **Señales**. Lea la entrada 1.4.0.0 de `CHANGELOG.md` antes de actualizar. Después:

1. Importe la solución.
2. En **Señales**, abra *Configuración de la lista → Columnas indexadas → Crear un índice nuevo* y cree uno para *SourceItemId* y otro para *Status*. Los sitios nuevos los reciben del kit de SharePoint.
3. Opcionalmente, cambie *tr_RetentionDays* (por defecto 90). Configúrelo antes de activar el flujo.
4. Active **VT Limpiar Señales**.

Las señales y los archivos de evidencia eliminados van a la papelera de reciclaje del sitio, desde donde se pueden restaurar durante 93 días (por verificar: aún no confirmado en un tenant).

### Límites conocidos de 1.3 (no verificados en un tenant)

Provienen del conocimiento de los conectores, no de una exportación real ni de una ejecución en un tenant:
- La configuración de las acciones de aprobación y los parámetros de `CopyFileAsync` (copia a `PublishedReports`) se construyeron a partir de la documentación del conector y no se han contrastado con una exportación real de un flujo.
- La `Path` que devuelven `GetFileMetadata` y el evento de carpeta creada (1.2), y el límite de 255 caracteres del vínculo al archivo guardado (1.2), siguen sin verificarse.
