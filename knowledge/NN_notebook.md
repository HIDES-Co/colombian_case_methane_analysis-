# Mapa de `scripts_2026/Scripts/NN.ipynb`

217 celdas (208 código, 9 markdown). No es un pipeline lineal: mezcla bloques de años
distintos (2018–2024), algunos comentados, y varias celdas dependen de estado producido
por ejecuciones previas de otras celdas. Ver también `scripts_2026/Scripts/README.md`
(documentación oficial de entorno/datos ya presente en el repo).

## Secciones, en orden de aparición

### 1. Alistamiento de datos (cruce espacial CH4 × cobertura de tierra)

- Carga geodataframes de cobertura de tierra IDEAM por año: `dfg_2018`, `dfg_2020`,
  `dfg_2022`, `dfg_2024` — la selección de qué años están activos/comentados es
  inconsistente y hay que revisarla antes de correr (ver README de `Scripts/`).
- Diccionarios de traducción de códigos de cobertura CORINE/IDEAM por nivel jerárquico:
  `mydict1`..`mydict6` (nivel 1 = territorios artificiales/agrícolas/bosques/áreas
  húmedas/superficies de agua, hasta nivel 6 el más granular).
- One-hot encoding de columnas `nivel_N` → `Leyenda_N_*` (función `get_encoded`).
- Cruce espacial pixel CH4 (buffer de 0.01°) × polígono de cobertura, calculando fracción
  de área por tipo de cobertura por píxel (`assign_landcover_sequential`,
  `compute_intersection_fractions`). Hay versiones comentadas en paralelo con
  `ThreadPoolExecutor`/`ProcessPoolExecutor` y un benchmark de workers/chunk_size —
  código muerto dejado in-place en vez de confiar en git history.
- Salida: `colombia_corr_<year>.csv` (ver `Datos_a_05-2026/`).

### 2. Inferencia causal

- Panel de diferencias año a año (Δcobertura vs Δ CH4).
- Lasso + OLS robusto (errores HC3) sobre los cambios de cobertura.
- Segunda pasada más elaborada: añade corrección FDR (Benjamini-Hochberg) y optimización
  de cutoff por validación cruzada.

### 3. Análisis de correlaciones

- Pearson simple + `pingouin.pairwise_corr` con corrección FDR.
- Ver `data_analysis/correlations.ipynb` para una versión con el mismo objetivo pero loop
  de intersección más vectorizado y rutas relativas.

### 4. Análisis de causalidad (threshold optimization)

- Funciones de optimización de umbral, con duplicados parcialmente comentados.

### 5. Clusters

- KMeans con `alpha_star = 3` fijo, **sin justificación de k** dentro del notebook.
- Contraste: `data_analysis/clusters.ipynb` calcula k óptimo con 4 métricas (elbow vía
  `KneeLocator`, silhouette, Calinski-Harabasz, Davies-Bouldin) + PCA — es la versión que
  debería usarse para justificar el valor de k en vez de repetirlo fijo aquí.

### 6. Clasificación (red neuronal)

- Red fully-connected de una capa oculta, `nn.MultiMarginLoss`, entrenada para predecir la
  región/departamento a partir de longitud/latitud.
- Modelo guardado como `data_analysis/mymodel_prueba2.pth`.

### 7. Series de tiempo (bloque comentado)

- Referencia funciones que ya no están definidas en el propio notebook — bloque huérfano.
- La versión funcional y madura de este análisis vive en `time series/timeSeries.ipynb`
  (ver `pipeline_stages.md`).

### 8. Detección de anomalías

- Autoencoder MLP con cuello de botella de 2 neuronas; el error de reconstrucción es el
  score de anomalía.
- Ploteo geográfico de anomalías positivas/negativas y cruce de anomalías con cobertura de
  tierra.
- Contraste: `data_analysis/deteccion_anomalias.ipynb` tiene la misma arquitectura pero con
  `prepare_data` reescrita (usa `RobustScaler`/`MinMaxScaler` y separa mejor el manejo de
  NaN antes de normalizar) — no está claro cuál preprocesamiento es el "vigente".

### 9. Suplemental — filtrado de "glint"

- Remueve píxeles sobre agua/humedales para evitar reflejo solar espurio (glint) sobre la
  medición TROPOMI.
- Implementado con loops `for j in df_s.index` **no vectorizados**, con comentarios tipo
  "correr hasta acá" que delatan el carácter de work-in-progress.
- Contraste: `time series/dataFiltering.ipynb` hace el mismo filtrado pero ya vectorizado
  con `isin()`/`set()`.

## Cosas a resolver antes de tratar este notebook como reproducible

- Sustituir rutas de Colab (`/content/drive/Shareddrives/PIGCC/...`) y la ruta absoluta
  `/home/hernan/...` por rutas relativas (`Path(...)`, ver ejemplo en el README de
  `Scripts/`).
- Decidir, para cada sección duplicada en `data_analysis/`, cuál versión es la fuente de
  verdad y cuál se debe dejar de mantener en `NN.ipynb` (detalle en
  `redundancias_e_inconsistencias.md`).
- El bloque de traducción (`deepl`, `DEEPL_AUTH_KEY`) es histórico y no forma parte del
  entorno reproducible declarado en `pyproject.toml`.
