# Recoleccion de datos desde Google Earth Engine

Este directorio contiene tres flujos con finalidades diferentes:

- `collect_gee_colombia.py`: recolector productivo de CH4, reanudable y verificable.
- `collect_covariates_gee.py`: recolector de covariables (DEM, albedo SWIR) en rasteres.
- `getCSV.ipynb`: notebook historico para exploracion; no se recomienda para descargas completas.

## Producto de metano

El script consulta `COPERNICUS/S5P/OFFL/L3_CH4` en la malla L3 publicada por
Earth Engine, aproximadamente 0.01 grados o 1.1 km. Cada imagen/orbita que
intersecta Colombia constituye una unidad de descarga independiente.

El proceso usa:

- `filterDate`, `filterBounds` y `select` antes de muestrear.
- `Image.sample()` en la proyeccion de la banda CH4 corregida, sin geometria por fila.
- `ee.data.computeFeatures()` con paginacion automatica.
- El endpoint `earthengine-highvolume` con ocho trabajadores por defecto.
- Un archivo Parquet atomico por imagen, particionado por año y mes.
- Reintentos con espera exponencial para errores transitorios.
- Validacion del esquema Parquet antes de omitir una imagen ya descargada.
- Bloqueo del directorio para impedir dos escritores concurrentes.

No se usa `ImageCollection.getRegion()` para los pixeles. El unico `getInfo()`
recupera la lista compacta de metadatos de las imagenes seleccionadas.

## Instalacion

Desde la raiz del repositorio:

```bash
uv sync
```

La escritura Parquet requiere `pyarrow`, declarado como dependencia directa.

Earth Engine necesita credenciales y un proyecto de Google Cloud registrado:

```bash
uv run earthengine authenticate
```

Tambien se puede solicitar la autenticacion desde el recolector con
`--authenticate`. En una VPS suele ser mas predecible autenticar una vez antes
de iniciar una descarga larga.

## Prueba minima

El final del intervalo es exclusivo. Este comando procesa como maximo una
imagen dentro de dos dias:

```bash
uv run python data_collection/collect_gee_colombia.py \
  --project ee-hides \
  --start 2024-01-01 \
  --end 2024-01-03 \
  --max-images 1
```

Para consultar solamente cuantas imagenes coinciden, sin crear salidas:

```bash
uv run python data_collection/collect_gee_colombia.py \
  --project ee-hides \
  --start 2024-01-01 \
  --end 2024-02-01 \
  --dry-run
```

El proyecto tambien puede configurarse sin incluirlo en el comando:

```bash
export EE_PROJECT=ee-hides
```

## Descarga completa

Ejemplo para la disponibilidad historica del producto hasta el inicio de 2026:

```bash
uv run python data_collection/collect_gee_colombia.py \
  --project ee-hides \
  --start 2019-02-08 \
  --end 2026-01-01 \
  --workers 8
```

No se recomienda subir `--workers` directamente a 40. Ocho solicitudes
concurrentes dejan margen para paginacion, reintentos y otros usuarios del
proyecto. El cliente de Earth Engine ya reintenta algunas respuestas HTTP 429;
el recolector reintenta la unidad de imagen completa si el error persiste.

## Salida

La ruta predeterminada es:

```text
data_collection/outputs/s5p_ch4/
  _collection_config.json
  _manifest.jsonl
  _last_run.json
  year=2019/
    month=02/
      <image-id>-<hash>.parquet
```

Los nombres de control comienzan por `_` para que PyArrow los ignore al leer
el directorio completo como un dataset Parquet:

```python
import pandas as pd

columns = [
    "id",
    "longitude",
    "latitude",
    "date",
    "CH4_column_volume_mixing_ratio_dry_air_bias_corrected",
]
ch4 = pd.read_parquet(
    "data_collection/outputs/s5p_ch4",
    columns=columns,
)
```

`date` es un timestamp UTC con zona horaria. `date_colombia` representa el
mismo instante en `America/Bogota`. `time` conserva los milisegundos Unix de
Earth Engine.

El esquema incluye las concentraciones corregida y no corregida, incertidumbre,
aerosoles, angulos solar/sensor y metadatos de producto. No se crean columnas
de geometria ni columnas de cobertura terrestre. Un valor ausente en una banda
auxiliar se conserva como nulo sin eliminar una observacion CH4 valida.
Esta politica forma parte de `_collection_config.json` para impedir que una
salida anterior con filtrado completo se reutilice silenciosamente.

## Reanudacion

Al reiniciar exactamente el mismo comando, cada Parquet existente se abre y se
valida. Si contiene exactamente los nombres y tipos esperados se omite; si esta
corrupto o tiene otro esquema se reemplaza atomicamente. Las imagenes validas
sin pixeles observados se representan mediante un Parquet de cero filas.

`_collection_config.json` impide mezclar en un mismo directorio ejecuciones con
bandas o filtros de calidad diferentes. Para cambiar `--bands` o
`--nominal-only`, se debe indicar otro `--output`.

`--overwrite` fuerza una nueva descarga de las imagenes seleccionadas, pero no
elimina otros periodos presentes en el directorio.

Una ejecucion termina con codigo distinto de cero si alguna imagen fallo. Las
imagenes correctas permanecen disponibles y se reutilizan en el siguiente
intento. `_manifest.jsonl` conserva eventos `completed`, `skipped` y `failed`.

## Calidad y limitaciones

- El producto comienza el 8 de febrero de 2019.
- No hay datos entre el 26 de julio y el 31 de agosto de 2022 por una interrupcion del proveedor.
- Earth Engine elimina en la ingestion los sondeos con validez menor o igual a 50 %, pero no publica `qa_value` como banda.
- La coleccion tampoco publica albedo SWIR ni clasificacion de superficie.
- Pueden permanecer franjas anomalas y observaciones problematicas sobre aguas interiores.
- La incertidumbre se conserva sin modificar; la documentacion del producto recomienda multiplicarla por dos cuando se necesita una estimacion global del error.
- La malla L3 es de 1.1 km, pero la resolucion fisica indicada para CH4 es aproximadamente 7 x 7 km. Las filas vecinas no deben tratarse automaticamente como sondeos fisicamente independientes.
- Antes de noviembre de 2021 el producto contiene XCH4 solo sobre tierra; despues se incorporaron observaciones oceanicas en modo glint.
- El limite administrativo GAUL 2015 tiene licencia para usos no comerciales.

No se recortan valores negativos ni se renombran errores de red como dias sin
datos. Los filtros cientificos adicionales deben aplicarse de forma explicita
y conservar sus parametros.

## Limites relevantes

- `ImageCollection.getRegion()`: 1,048,576 valores por llamada.
- Peticiones interactivas: aproximadamente cinco minutos y decenas de MB.
- Cuota predeterminada: 40 peticiones concurrentes y 100 peticiones por segundo.
- `computeFeatures()`: 1,000 filas por pagina por defecto; el script solicita 5,000.
- Resultado de una agregacion: 100 MiB.
- Payload de una consulta: 10 MB.
- Las cuotas mensuales no comerciales de Earth Engine tambien aplican a la API de Python.

Referencias oficiales:

- [Catalogo Sentinel-5P CH4](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_CH4)
- [Cuotas de Earth Engine](https://developers.google.com/earth-engine/guides/usage)
- [Entornos de procesamiento](https://developers.google.com/earth-engine/guides/processing_environments)
- [Extraccion de datos](https://developers.google.com/earth-engine/guides/data_extraction)
- [`computeFeatures`](https://developers.google.com/earth-engine/apidocs/ee-data-computefeatures)
- [`Image.sample`](https://developers.google.com/earth-engine/apidocs/ee-image-sample)

## Covariables (DEM y albedo SWIR)

`collect_covariates_gee.py` implementa el paso 1 del plan 01 y el paso 2 del
plan 02: exporta GeoTIFF reducidos a la malla harp de 0.01 y 0.06 grados
(el mismo origen -120.0 / 50.0 del producto de CH4), recortados a Colombia
mediante `ee.data.computePixels`, y los muestrea localmente en los centros de
pixel de la malla CH4. Nunca envia los ~700 k puntos a Earth Engine.

```bash
# DEM: 6 GeoTIFF estaticos + columnas elev_* en covariables/estaticas_0p01.parquet
uv run python data_collection/collect_covariates_gee.py \
  --project ee-hides --layer dem

# Albedo SWIR MCD43A3: medias mensuales 2019-01..2025-12 y anuales 2022/2024
uv run python data_collection/collect_covariates_gee.py \
  --project ee-hides --layer albedo_swir --start 2019-01 --end 2026-01
```

Salidas de analisis en `scripts_2026/Datos_a_05-2026/covariables/`
(`estaticas_0p01.parquet`, `mensuales/albedo_swir_0p01.parquet`, cada una con
su `.json` hermano de procedencia). Rasteres intermedios reanudables en
`data_collection/outputs/covariables/<capa>/` con el mismo esquema de
manifiesto y configuracion que el recolector de CH4. `--dry-run` lista lo
pendiente, `--skip-sample` solo descarga, `--sample-only` solo reconstruye los
parquet desde los rasteres presentes. La union en el analisis se hace
exclusivamente con `common.covariables.unir_covariables`; las fichas por
variable estan en `knowledge/covariables.md`.

## Meteorologia

La meteorologia todavia no forma parte del recolector productivo. Su
incorporacion (variables priorizadas por impacto, reglas de union temporal y
espacial, convenciones de procedencia, pruebas de rendimiento y criterios de
aceptacion) esta definida en el plan de trabajo
[`plans/active/06_meteorologia_era5.md`](../plans/active/06_meteorologia_era5.md),
que reemplaza al antiguo `METEOROLOGY_PLAN.md`.
