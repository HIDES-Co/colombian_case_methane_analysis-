# Pipelines por subdirectorio y su relación con `NN.ipynb`

## `data_collection/getCSV.ipynb` — recolección (etapa previa a todo)

Usa `common/satelite.py` (`ColSatellite`) para autenticar Google Earth Engine, particiona
los departamentos de Colombia (`FAO/GAUL_SIMPLIFIED_500m/2015/level1`) en 16 ROIs para
evitar límites de cuota, y descarga día a día el producto
`COPERNICUS/S5P/OFFL/L3_CH4` (capa `CH4_column_volume_mixing_ratio_dry_air_bias_corrected`)
a CSVs en `csvResults/`.

**Relación con `NN.ipynb`:** es la etapa de recolección que precede a todo — produce los
CSV crudos que, tras una agregación mensual/anual no versionada en el repo, se convierten
en `colombia_prom_<year>.csv`, la entrada real de `NN.ipynb`.

**Estado:** funcional. Nota: usa un proyecto de Earth Engine distinto (`ee-hides`) al
declarado en `common/satelite.py` (`ee-jolejua`) — revisar antes de reejecutar.

## `surface_retrieve/` — línea paralela, NO integrada

- `EGG4_handling.ipynb`: lee GRIB del reanálisis atmosférico CAMS EGG4 (perfiles de CH4 por
  nivel de presión) con `pygrib`, calcula columna promedio ponderada por ΔP y la razón
  "nivel/columna" — busca entender cuánto aporta cada altura a la columna total que mide
  TROPOMI.
- `vertical_methane_profile.py`: utilidad standalone de inspección/plot de un GRIB (usa
  `Basemap`, que **no está declarado en `pyproject.toml`** — solo `pygrib` está en el
  grupo `surface`).

**Relación con `NN.ipynb`:** investigación paralela e independiente sobre el sesgo
vertical de la medición L3 (columna total vs. perfil). `NN.ipynb` usa directamente la
capa `_bias_corrected` sin considerar el perfil vertical — este trabajo no está
incorporado aguas abajo todavía.

**Estado:** el más crudo/exploratorio de todo el repo — sin markdown, con prints de debug,
sin conexión de código con el resto del proyecto.

## `time series/` — el pipeline más maduro del repo

Progresión clara en tres archivos:

1. `dataFiltering.ipynb`: réplica temprana, ya vectorizada (`isin()`/`set()`), de la
   sección "Suplemental" de `NN.ipynb` (filtrado de glint: encoding de cobertura, buffer
   de píxel, intersección con polígonos de agua/humedal).
2. `timeSeries copy.ipynb`: versión más temprana/menos pulida del análisis de series de
   tiempo (labels en español, sin comparación externa).
3. `timeSeries.ipynb`: sucesora directa de la anterior (confirmado por diff línea a línea)
   — añade bandas de confianza al 95%, tendencia LOWESS + pendiente anual, overlay del
   índice ENSO, y comparación contra estación terrestre NOAA (Barbados, `CH4_completo.csv`)
   y promedio global (`ch4_mm_gl.csv`) con un factor de escala (~1.0395) para reconciliar
   el satélite con mediciones in-situ.

**Relación con `NN.ipynb`:** consume `colombia_results_total_filtrado.csv` y
`mean_values_clustered_v1.csv` — depende de que ya exista una salida de clustering (como
la de `NN.ipynb` o `data_analysis/clusters.ipynb`) para etiquetar cada punto por región.
Es, junto con `data_analysis/clusters.ipynb`, el candidato más fuerte a resultado
presentable del proyecto: nombres de variable limpios, docstrings, validación cruzada de
coordenadas entre datasets.

## `data_analysis/` — versiones "optimizadas" por tema, extraídas de `NN.ipynb`

- **`clusters.ipynb`**: a diferencia de `NN.ipynb` (que fija `alpha_star=3` sin evidencia),
  calcula k óptimo con 4 métricas simultáneas (elbow vía `KneeLocator`, silhouette,
  Calinski-Harabasz, Davies-Bouldin) + visualización PCA de los clusters.
- **`correlations.ipynb`**: mismo cruce espacial CH4 × cobertura que `NN.ipynb`, con el
  loop de intersección algo más optimizado (`.at[]`, geometrías precomputadas) y rutas
  relativas a `common_path`/`satellite_csv_data` en vez de rutas de Drive/absolutas.
- **`deteccion_anomalias.ipynb`**: mismo autoencoder MLP que `NN.ipynb`, con `prepare_data`
  reescrita dos veces dentro del propio notebook (la segunda versión usa
  `RobustScaler`/`MinMaxScaler` y separa mejor el manejo de NaN antes de normalizar) —
  evidencia de iteración activa sobre la robustez del preprocesamiento. Añade también la
  sección "Land cover vs anomalies" (cruce explícito anomalías-cobertura), igual que
  `NN.ipynb`.

**Estado:** más enfocados que `NN.ipynb` (una sola tarea por notebook), pero todavía leen
CSVs con rutas relativas simples (`colombia_prom_filtered.csv`, sin `Path`/`DATA_DIR`), así
que tampoco son ejecutables sin ajustar rutas.

Modelos guardados en este directorio (`.pth`, ignorados por git): `best_model.pth`,
`mymodel_prueba.pth`, `mymodel_prueba2.pth`, `mymodel_prueba_corrected_filtered.pth`,
`mymodel_prueba_v2.pth` — corresponden a distintas corridas del autoencoder y/o del
clasificador de `NN.ipynb`; no hay un registro de cuál es el "mejor" vigente más allá del
nombre `best_model.pth`.

## `temp_correlations_clusters_dataAnalysis.ipynb` (raíz del repo)

Tiene exactamente la misma estructura de secciones que `NN.ipynb` (Alistamiento →
Correlaciones → Clusters → Clasificación → Series de tiempo → Detección de anomalías →
Suplemental), pero condensada en 124 celdas vs. 217. Es, con alta probabilidad, **un
snapshot intermedio de `NN.ipynb`** — el eslabón entre el monolito original y la posterior
separación por tema en `data_analysis/`. No aporta nada que no esté ya en `NN.ipynb` o en
las versiones optimizadas de `data_analysis/`.

## `common/satelite.py` y `all_data_plotting/plotting.py`

`satelite.py` define `Satellite`/`ColSatellite` (wrapper de Earth Engine, usado por
`getCSV.ipynb`) y `csv_from_sat`/`statAnalisisData` (ploteo geográfico +
**kriging/variogramas con `gstools`**: ajuste de 13 modelos de variograma e interpolación
ordinaria por partición geométrica).

**Relación con `NN.ipynb`:** este método geoestadístico (kriging) **no se usa en ninguna
parte de `NN.ipynb`**, que resuelve el problema de "cobertura por píxel" con intersección
exacta de polígonos — son dos enfoques alternativos no reconciliados para relacionar CH4
con el espacio.

`plotting.py` es un script consumidor de `csv_from_sat` que genera el mapa nacional de CH4
promedio 2019–2024 sobre un CSV fijo de `time series/`.
