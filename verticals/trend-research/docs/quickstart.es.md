# Vigilante de Tendencias: guía de inicio rápido

Esta guía instala el Vigilante de Tendencias en su tenant de Microsoft 365 en unos 45 minutos. Al terminar tendrá tres flujos automáticos:

| Flujo | Cuándo se ejecuta (UTC) | Qué hace |
|---|---|---|
| **VT Recolectar RSS** | Todos los días, 11:00 | Lee las fuentes RSS habilitadas y guarda cada artículo nuevo como evidencia. |
| **VT Clasificar Elementos** | Todos los días, 16:00 | Evalúa cada artículo nuevo frente a cada brief habilitado y crea una señal. |
| **VT Resumen Semanal** | Lunes, 08:00 | Publica un resumen HTML por brief y le avisa por Teams. |

## Qué necesita

- Dos archivos de la versión publicada (carpeta `releases/trend-research/<versión>/`):
  - `TrendResearchFlow_<versión>_es.zip`: la solución de Power Platform. **No lo descomprima.**
  - `TrendResearchFlow_<versión>_es_sharepoint.zip`: el kit de SharePoint. **Descomprímalo.**
- Un entorno de Power Platform con Dataverse y licencia de Copilot Studio (flujos de agente).
- Si el idioma base del entorno no es español, el paquete de idioma español habilitado en el entorno.
- Permiso para crear sitios de SharePoint, o un sitio ya creado del que sea propietario.

## 1. Cree el sitio de SharePoint

1. En SharePoint, seleccione **Crear sitio → Sitio de grupo**. Use un nombre como `Vigilante de Tendencias` y privacidad **Privado**.
2. Copie la URL del sitio, por ejemplo `https://contoso.sharepoint.com/sites/VigilanteTendencias`. La necesitará en los pasos 2 y 3.

## 2. Cree las listas y bibliotecas (elija una opción)

Los flujos dependen del **nombre interno** de cada columna (por ejemplo `field_3`), no del nombre visible. Las dos opciones crean las mismas cinco listas (`Briefs`, `Fuentes`, `ElementosFuente`, `Señales`, `Publicaciones`) y las cuatro bibliotecas (`Evidence`, `PublishedReports`, `ResearchDrafts`, `SourceUploads`).

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

`Fuentes` y `Briefs` incluyen filas de ejemplo: nueve feeds RSS públicos y un brief sobre IA de voz. Edítelas o elimínelas en el paso 5.

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
2. Vaya a **Soluciones → Importar solución → Examinar**, elija `TrendResearchFlow_<versión>_es.zip` y seleccione **Siguiente**.
3. **Conexiones.** Para cada referencia de conexión, elija una conexión existente o cree una nueva con la cuenta de servicio acordada:

   | Referencia | Conector | Cuenta |
   |---|---|---|
   | Vigilante de Tendencias - SharePoint | SharePoint | Con lectura y escritura en el sitio del paso 1 |
   | Vigilante de Tendencias - RSS | RSS | No requiere cuenta |
   | Vigilante de Tendencias - Teams | Microsoft Teams | Quien recibirá el aviso del resumen |
   | Vigilante de Tendencias - Clasificador IA | Agente de Copilot Studio | La cuenta con licencia de Copilot Studio |

4. **Variables de entorno.**

   | Variable | Valor |
   |---|---|
   | URL del sitio | La URL del paso 1, sin barra final |
   | Lista de briefs / fuentes / elementos fuente / señales / publicaciones | Ya vienen con `Briefs`, `Fuentes`, `ElementosFuente`, `Señales`, `Publicaciones`. Cámbielas solo si usó otros nombres de lista. También acepta el ID (GUID) de la lista. |
   | Límite diario de clasificación | `50` (máximo de elementos clasificados por día). Cada elemento se clasifica una vez por brief habilitado. |
   | Biblioteca de cargas de fuentes | Ya viene con el título de la biblioteca (`Cargas de fuentes`). Si el desencadenador del flujo rechaza el título, escriba el ID (GUID) de la biblioteca. |
   | Tamaño máximo de carga (bytes) | `1000000`. Los archivos más grandes se registran solo por nombre (vea el paso 5). |

   El resto de variables están reservadas para versiones futuras. Déjelas vacías.

5. Seleccione **Importar** y espere el mensaje de éxito (1 o 2 minutos).

## 4. Active los flujos

1. En **Soluciones**, abra **Vigilante de Tendencias → Flujos de nube**.
2. Compruebe que **VT Recolectar RSS**, **VT Clasificar Elementos**, **VT Resumen Semanal** y **VT Procesar Documentos** están **Activados**. Si alguno aparece desactivado, selecciónelo y elija **Activar**.

Los mismos flujos aparecen en Copilot Studio en **Flujos**.

## 5. Configure su investigación

- **Briefs**: edite el brief de ejemplo o cree uno nuevo. Complete *Pregunta*, *Palabras clave*, *Exclusiones*, *Idiomas* y *Geografías*. Use `1` en *Habilitado* para activarlo y `0` para desactivarlo. Si cambia la pregunta de un brief existente, aumente *Versión del brief*: los elementos nuevos se analizarán con la versión nueva.
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

## 6. Pruebe de punta a punta

Ejecute cada flujo una vez con **Probar → Manualmente**, en este orden:

1. **VT Recolectar RSS** → aparecen filas en **ElementosFuente** con *Estado* `Ready` y archivos `.txt` en **Evidencias**.
2. **VT Clasificar Elementos** → aparecen filas en **Señales**. Los elementos procesados cambian a `Classified`.
3. **VT Resumen Semanal** → aparece un archivo HTML en **Informes publicados** y una fila en **Publicaciones**, y recibe un mensaje en Teams. Si ninguna señal llegó a relevancia 70 o más en los últimos 7 días, no se genera resumen. Es el comportamiento esperado.
4. **VT Procesar Documentos** (si agregó una fuente `Upload`) se ejecuta sola cuando se agrega un archivo. Cargue un `.txt` pequeño en la subcarpeta de la fuente y espere unos 5 minutos. Aparecen un ElementoFuente con *ContentStatus* `FullText` y un archivo en **Evidencias**.

Las columnas de estado (*Estado*, *Impacto*, *Horizonte*) guardan códigos en inglés (`Ready`, `Digest`, `High`…) a propósito: los flujos filtran por esos valores. El resumen HTML los muestra traducidos.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `List not found` o `Lista no encontrada` | El nombre de la lista no coincide con la variable de entorno. Corrija la variable (o use el GUID de la lista) y luego **desactive y active** el flujo. |
| `Column 'field_N' does not exist` | La columna no tiene el nombre interno esperado. Ejecute `provision.ps1 -VerifyOnly` o revise el paso 2. |
| Cambié una variable de entorno y el flujo sigue usando el valor anterior | Desactive y vuelva a activar el flujo. El cambio puede tardar hasta una hora en propagarse. |
| `Input exceeds the maximum length of 255` | Una columna de texto largo se creó como texto de una línea. Ejecute `provision.ps1 -VerifyOnly` para encontrarla. |

## Actualizar a una versión nueva

Importe el zip nuevo con **Soluciones → Importar solución**, igual que en el paso 3. La solución se actualiza en su lugar. Sus listas, datos y valores de variables de entorno se conservan. Si usó la opción B, vuelva a ejecutar `provision.ps1` del kit nuevo: agrega las columnas nuevas. Con la opción A, agréguelas a mano según las notas de la versión.

### Actualizar de 1.1 a 1.2

1.2.0.0 agrega el flujo `VT Procesar Documentos`, la biblioteca `SourceUploads` y la columna `SourcePath` en **Fuentes**. Siga el archivo `upgrade-1.2.0.0.es.md` que genera la compilación, dentro del zip del kit de SharePoint: indica qué agregar a mano si usó la opción A. Después:

1. Cree la biblioteca `SourceUploads` y su carpeta `PublicData` (la opción B lo hace al ejecutar `provision.ps1`).
2. Importe la solución nueva. Pedirá las dos variables de entorno nuevas, *Biblioteca de cargas de fuentes* y *Tamaño máximo de carga*.
3. Active **VT Procesar Documentos** y agregue filas `Upload` en **Fuentes** (paso 5).
4. Lea la entrada 1.2.0.0 de `CHANGELOG.md` antes de actualizar. Describe la corrección del ItemKey en `VT Recolectar RSS`; su efecto sobre los elementos existentes está pendiente de verificación en el tenant de desarrollo.

