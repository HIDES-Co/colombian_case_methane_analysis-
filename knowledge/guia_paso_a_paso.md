# Guía paso a paso para retomar el repositorio

Esta guía te lleva por el repo en el orden en que conviene reconstruir el contexto,
combinando lectura de código y de los documentos ya escritos en `knowledge/`. Cada paso
tiene un objetivo, qué abrir, y una casilla de verificación de que entendiste lo esencial
antes de avanzar.

> Nota de estado: `scripts_2026/Scripts/NN.ipynb` tiene cambios sin commitear frente al
> último commit (`74c8284`, "Documentar ejecución de NN y excluir datos pesados"): +3026/-1413
> líneas, mismo número de celdas (217). La estructura de secciones no cambió, pero el
> contenido dentro de varias celdas sí — por eso el Paso 3 te pide comparar contra lo
> documentado, no solo confiar en `NN_notebook.md` a ciegas.

---

## Paso 0 — Entorno

Antes de abrir nada, monta el entorno para poder ejecutar celdas si quieres probar algo.

```bash
uv sync --group notebooks --group analysis
```

**Este repositorio se trabaja desde una VPS**, así que `uv run jupyter lab` a secas no
sirve: intenta abrir un navegador en la propia VPS y no hay entorno gráfico ahí. Usa en su
lugar:

```bash
uv run jupyter lab --no-browser --ip=0.0.0.0 --port=8888 --allow-root
```

y, desde tu máquina local, un túnel SSH hacia ese puerto:

```bash
ssh -N -L 8888:localhost:8888 usuario@ip-de-la-vps
```

Con el túnel abierto, entra a `http://localhost:8888/lab?token=...` (el token lo imprime
la consola de la VPS al arrancar JupyterLab) desde el navegador de tu máquina local.
Alternativa equivalente: conectarte a la VPS con Remote-SSH de VS Code/Cursor o JetBrains
Gateway y abrir `NN.ipynb` ahí directamente, sin túnel manual. El detalle completo está en
el `README.md` de la raíz ("Trabajando desde una VPS") y en
`scripts_2026/Scripts/README.md`.

Lee esos dos README — son cortos y explican además qué grupos de `uv` necesitas y qué
rutas de datos hay que adaptar. No los repito aquí.

**Checkpoint:** sabes qué grupo de dependencias activar, cómo vas a abrir JupyterLab desde
la VPS (túnel SSH o editor remoto) y dónde deberían vivir los CSV de `Datos_a_05-2026/`
localmente.

---

## Paso 1 — Panorama general (5 min)

Abre [`README.md`](./README.md) de esta carpeta. Es el mapa de alto nivel: el diagrama de
flujo de datos completo (`getCSV.ipynb` → agregación → `colombia_prom_<year>.csv` →
`NN.ipynb` → notebooks derivados) y una tabla de contenidos de los demás documentos.

**Checkpoint:** puedes dibujar de memoria, sin mirar, la cadena
`recolección → NN.ipynb → (data_analysis | time series)`.

---

## Paso 2 — Cómo llegan los datos a `NN.ipynb`

Antes de entrar al notebook principal, entiende su insumo:

1. `data_collection/getCSV.ipynb` — recolección desde Google Earth Engine
   (`COPERNICUS/S5P/OFFL/L3_CH4`), particionada por departamento en 16 ROIs.
2. `common/satelite.py` — la clase `ColSatellite` que usa el notebook anterior. Fíjate en
   el identificador de proyecto EE (`ee-jolejua` aquí vs. `ee-hides` en `getCSV.ipynb` —
   inconsistencia ya anotada, revisa cuál es el vigente antes de reautenticar).
3. (Opcional, línea paralela no integrada) `surface_retrieve/EGG4_handling.ipynb` y
   `vertical_methane_profile.py` — perfil vertical CAMS/EGG4. Solo revísalo si te interesa
   el sesgo vertical de la columna medida; no alimenta a `NN.ipynb`.

Lee la sección correspondiente en [`pipeline_stages.md`](./pipeline_stages.md)
("`data_collection/getCSV.ipynb`" y "`surface_retrieve/`") para el detalle ya escrito.

**Checkpoint:** entiendes que `colombia_prom_<year>.csv` (en `Datos_a_05-2026/`) es el
punto de entrada real de `NN.ipynb`, y que no hay un script versionado que documente cómo
se pasa de los CSV diarios de `getCSV.ipynb` a esos promedios anuales (gap conocido).

---

## Paso 3 — `NN.ipynb`, sección por sección

Este es el núcleo. Ábrelo en Jupyter y ve sección por sección; en cada una, primero relee
el resumen correspondiente en [`NN_notebook.md`](./NN_notebook.md) y luego compara contra
las celdas reales indicadas (los números de celda son del árbol actual del notebook,
0-indexado, contando también las celdas de código intercaladas).

| # | Sección (celda markdown) | Rango de celdas aprox. | Qué verificar dado que hubo cambios sin commitear |
|---|---|---|---|
| 1 | Alistamiento de datos (celda 2) | 2–48 | Qué años (`dfg_2018/2020/2022/2024`) están activos/comentados **ahora**; puede haber cambiado respecto a lo descrito en `NN_notebook.md` |
| 2 | Inferencia Causal (celda 49) | 49–50 | Si sigue el mismo Lasso+OLS HC3, o si el pase de FDR/CV se movió |
| 3 | Análisis de correlaciones (celda 51) | 51–64 | Comparar con `data_analysis/correlations.ipynb` (Paso 4) |
| 4 | Análisis de causalidad (celda 65) | 65–97 | Revisar si los duplicados comentados de optimización de threshold siguen ahí |
| 5 | Clusters (celda 98) | 98–105 | Confirmar si `alpha_star` sigue fijo en 3 o si ya se parametrizó con el k óptimo de `data_analysis/clusters.ipynb` |
| 6 | Clasificación (celda 106) | 106–126 | Revisar si el modelo guardado sigue siendo `mymodel_prueba2.pth` |
| 7 | Series de tiempo (celda 127) | 127–150 | Sigue siendo un bloque huérfano (referencia funciones no definidas ahí)? |
| 8 | Detección de anomalías (celda 151) | 151–169 | Comparar `prepare_data` contra la versión de `data_analysis/deteccion_anomalias.ipynb` (Paso 4) |
| 9 | Suplemental — filtrado de glint (celda 170) | 170–216 | Sigue con loops `for j in df_s.index` sin vectorizar, o se vectorizó como en `time series/dataFiltering.ipynb`? |

Truco para no perderte: en Jupyter usa la barra lateral de Table of Contents (los headers
markdown de arriba aparecen ahí) para saltar directo a cada sección en vez de scrollear
217 celdas.

**Checkpoint:** por cada sección de la tabla, anota mentalmente (o en un scratch aparte) si
lo que ves coincide con `NN_notebook.md` o si el notebook avanzó — eso te dice qué parte de
la documentación hay que actualizar al final.

---

## Paso 4 — Versiones "optimizadas" por tema

Ahora que ya viste cómo está cada sección en el monolito, mira sus contrapartes más
pulidas. Abre en paralelo (no hace falta ejecutar, solo leer):

- `data_analysis/clusters.ipynb` — mismo problema que la sección 5 de `NN.ipynb`, pero con
  k óptimo justificado (elbow/silhouette/Calinski-Harabasz/Davies-Bouldin + PCA).
- `data_analysis/correlations.ipynb` — mismo problema que la sección 3, loop más
  vectorizado y rutas relativas.
- `data_analysis/deteccion_anomalias.ipynb` — mismo problema que la sección 8, con
  `prepare_data` reescrita usando `RobustScaler`/`MinMaxScaler`.

Lee la parte "`data_analysis/`" de [`pipeline_stages.md`](./pipeline_stages.md) si quieres
el resumen ya redactado en vez de releer los notebooks completos.

**Checkpoint:** para cada una de las tres parejas (NN.ipynb-sección ↔ data_analysis-notebook),
tienes claro cuál versión usarías hoy si tuvieras que producir un resultado nuevo.

---

## Paso 5 — El pipeline más maduro: `time series/`

Lee en orden (son progresivamente mejores, confirmado por diff línea a línea):

1. `time series/dataFiltering.ipynb` — filtrado de glint vectorizado (contraparte de la
   sección 9/Suplemental de `NN.ipynb`).
2. `time series/timeSeries copy.ipynb` — versión temprana del análisis temporal.
3. `time series/timeSeries.ipynb` — versión final: bandas de confianza, tendencia LOWESS,
   overlay ENSO, comparación contra NOAA y promedio global.

**Checkpoint:** entiendes que este notebook depende de que ya exista una salida de
clustering (de `NN.ipynb` o de `data_analysis/clusters.ipynb`) para etiquetar cada punto
por región — no es standalone.

---

## Paso 6 — `common/` y el enfoque geoestadístico no reconciliado

Lee `common/satelite.py` (clases `Satellite`/`ColSatellite`/`csv_from_sat`/`statAnalisisData`)
y `all_data_plotting/plotting.py`. El punto clave: aquí se usa **kriging con variogramas**
(`gstools`) para interpolar CH4 en el espacio, un enfoque que **`NN.ipynb` no usa en
ningún momento** (allí se resuelve con intersección exacta de polígonos de cobertura).
Vale la pena decidir conscientemente si esto sigue siendo relevante o es una rama muerta.

**Checkpoint:** puedes explicar la diferencia entre "intersección de polígonos de
cobertura" (usado en `NN.ipynb`) y "kriging/variograma" (usado en `common/`) como dos
formas distintas de responder "¿cuánto CH4 hay en este punto/región?".

---

## Paso 7 — Snapshot intermedio (opcional)

Si tienes curiosidad histórica, ojea `temp_correlations_clusters_dataAnalysis.ipynb`
(raíz del repo) — mismo esqueleto de secciones que `NN.ipynb` pero con 124 celdas en vez
de 217. Es candidato a ser un snapshot ya superado; no es necesario para seguir
trabajando, pero puede ayudar a rastrear cuándo se separaron los notebooks de
`data_analysis/`.

---

## Paso 8 — Cierre: reconciliar inconsistencias

Termina con [`redundancias_e_inconsistencias.md`](./redundancias_e_inconsistencias.md) —
la lista de 8 puntos de duplicación/decisiones no reconciliadas. Con todo el contexto
fresco de los pasos anteriores, esta lista debería leerse rápido y servir como backlog de
decisiones a tomar (cuál versión de cada análisis es la vigente, si vale la pena
consolidar la lógica de cruce espacial/glint en `common/`, etc.).

**Checkpoint final:** tienes una lista propia (mental o escrita) de qué de
`redundancias_e_inconsistencias.md` sigue vigente y qué ya cambió con los edits recientes
de `NN.ipynb` — eso es lo primero que deberíamos actualizar en `knowledge/` una vez lo
confirmes.
