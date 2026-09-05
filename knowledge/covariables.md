# Covariables del análisis CH₄ — fichas por variable

Creado por el paso 1 del plan 01 (infraestructura de covariables). Cada plan
cerrado añade o actualiza aquí la ficha de sus variables (plan maestro §4).

**Convenciones comunes**

- Malla: rejilla harp del producto S5P L3 — origen lon −120.0, lat 50.0,
  paso 0.01° (centros de píxel en `.xx5`); la malla de 0.06° comparte origen y
  anida exactamente 6×6 celdas de 0.01°.
- Descarga: `data_collection/collect_covariates_gee.py` exporta GeoTIFF por
  (capa, estadística, resolución, periodo) con `ee.data.computePixels` y los
  muestrea localmente en los centros de píxel de la malla CH₄ (coordenadas
  únicas de `CH4_glintfiltered_colombia_2019-2026.csv`, cacheadas en
  `covariables/malla_ch4_0p01.parquet`).
- Salidas: `scripts_2026/Datos_a_05-2026/covariables/estaticas_0p01.parquet`
  (una fila por píxel) y `covariables/mensuales/<variable>_0p01.parquet`
  (una fila por píxel-mes). Cada parquet tiene un `.json` hermano con fuente,
  máscara, licencia y fecha exacta de descarga.
- Unión: **solo** con `common.covariables.unir_covariables(df, nombres)`
  (redondeo a 5 decimales; falla si un píxel queda sin covariable estática).
  Nombres mensuales terminan en `_mensual` (p. ej. `albedo_swir_mensual`).
- Rásteres intermedios: `data_collection/outputs/covariables/<capa>/` con
  `_collection_config.json`, `_manifest.jsonl` y `_last_run.json` (reanudable).

## Elevación y rugosidad (plan 01)

| Campo | Valor |
|---|---|
| Columnas | `elev_m`, `elev_std_1km` (0.01°); `elev_std_7km`, `elev_min_7km`, `elev_max_7km` (0.06°, asignadas al píxel de 0.01° por celda contenedora) |
| Fuente | `COPERNICUS/DEM/GLO30`, banda `DEM`, 30 m |
| Reductores | media y desviación típica a 0.01°; media, desviación, mín y máx a 0.06° (`reduceResolution`) |
| Vertical | altura sobre el geoide EGM2008 |
| Temporalidad | estática |
| Sin dato | píxeles CH₄ sobre océano/costa sin dato GLO30 se rellenan con 0 m; el conteo queda en `estaticas_0p01.json → variables.dem_glo30.relleno_oceano_0m` |
| Auxiliares | `elev_res_nativa_m` = 30; `celda_0p06_id` = fila·100000+columna de la celda 0.06° (agrupar errores por celda fuente, plan 03) |
| Licencia | Copernicus DEM GLO-30 (ESA/Airbus): uso libre con atribución |
| Papel | §3: confusor dominante (−3 a −8 ppb/km esperado). §4: se cancela al diferenciar (verificarlo). `elev_std_7km` es covariable de calidad del retrieval (DEM malo en terreno rugoso) |

## Albedo SWIR (plan 02)

| Campo | Valor |
|---|---|
| Columnas estáticas | `albedo_swir_<año>` (BSA), `albedo_swir_wsa_<año>`; por defecto años 2022 y 2024 |
| Columnas mensuales | `albedo_swir`, `albedo_swir_wsa`, `albedo_swir_n_obs` en `mensuales/albedo_swir_0p01.parquet` |
| Fuente | `MODIS/061/MCD43A3`, bandas `Albedo_BSA_Band7` / `Albedo_WSA_Band7`, 500 m, diario, escala 0.001 aplicada |
| Máscara | `BRDF_Albedo_Band_Mandatory_Quality_Band7 ≤ 0` (solo inversión BRDF completa; `--qa-max 1` para relajar) |
| Agregación | media de los días QA-válidos del mes/año y `reduceResolution(mean)` a 0.01° y 0.06°; `n_obs` = media de días válidos |
| Filas mensuales | se descartan los píxeles-mes sin BSA ni WSA (océano o sin inversión); `n_obs` = 0 cuando ningún día pasó la máscara |
| Auxiliar | `albedo_swir_res_nativa_m` = 500 |
| Licencia | NASA LP DAAC, dominio público |
| **Advertencias** | Banda 7 = **2.1 µm**: proxy espectral cercano, **no** el albedo de 2.3 µm que usa el retrieval de CH₄ (declararlo en métodos, plan 02 §7). La deriva orbital de Aqua desde ~2022 puede reducir `n_obs`. El albedo es consecuencia del cambio de cobertura: controlar por él puede sobrecontrolar (mediador); reportar especificaciones con y sin él |
| Papel | §4: el sesgo residual del retrieval con el albedo **no se cancela** al diferenciar porque cambia con el tratamiento (bosque oscuro → pasto claro). Validar primero el proxy interno `dry_air − bias_corrected` contra estas columnas (plan 02, paso 2) |
