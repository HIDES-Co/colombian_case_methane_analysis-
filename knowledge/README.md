# Guía de navegación del repositorio

Esta guía explica cómo está organizado el proyecto de análisis de metano en Colombia
(datos nivel 3 de Copernicus Sentinel-5P TROPOMI), con `scripts_2026/Scripts/NN.ipynb`
como eje central, y cómo se relaciona con los pipelines de cada subdirectorio.

Documentos de esta carpeta:

- [`NN_notebook.md`](./NN_notebook.md) — mapa detallado de las secciones de `NN.ipynb`.
- [`pipeline_stages.md`](./pipeline_stages.md) — qué hace cada subdirectorio y cómo se
  conecta con `NN.ipynb` (predecesor, sucesor, versión optimizada o línea paralela).
- [`redundancias_e_inconsistencias.md`](./redundancias_e_inconsistencias.md) — puntos de
  duplicación de lógica y decisiones no reconciliadas entre notebooks, útil como lista de
  candidatos a refactor/consolidación.

## Flujo de datos de extremo a extremo

```
data_collection/getCSV.ipynb (Google Earth Engine, TROPOMI L3 CH4)
        │  descarga diaria/departamental → csvResults/*.csv
        ▼
[agregación mensual/anual, no versionada en el repo]
        │
        ▼
scripts_2026/Datos_a_05-2026/colombia_prom_<year>.csv   ← entrada real de NN.ipynb
        │
        ├──► surface_retrieve/ (EGG4_handling.ipynb, vertical_methane_profile.py)
        │       investigación paralela del perfil vertical CAMS/EGG4 (GRIB, pygrib).
        │       NO está integrada en NN.ipynb ni en el resto del repo.
        │
        ▼
scripts_2026/Scripts/NN.ipynb   ◄── EJE DEL PROYECTO (monolito exploratorio, 217 celdas)
        │   cruce con cobertura de tierra IDEAM → encoding → inferencia causal →
        │   correlaciones → clusters → clasificación NN → autoencoder de anomalías →
        │   filtrado de "glint"
        │
        ├──► temp_correlations_clusters_dataAnalysis.ipynb
        │       snapshot intermedio (124 celdas) con la misma estructura de secciones;
        │       probable antecesor directo de la separación en data_analysis/.
        │
        ├──► data_analysis/clusters.ipynb           (misma tarea, k óptimo justificado)
        ├──► data_analysis/correlations.ipynb       (misma tarea, loop más vectorizado)
        ├──► data_analysis/deteccion_anomalias.ipynb (mismo autoencoder, preprocesamiento mejorado)
        │
        └──► time series/dataFiltering.ipynb
                 → time series/timeSeries copy.ipynb
                 → time series/timeSeries.ipynb
             (filtrado de glint vectorizado → comparación con estaciones NOAA e índice ENSO;
              el pipeline más maduro/presentable del repo)

common/satelite.py ──► usado por getCSV.ipynb y all_data_plotting/plotting.py
                        (kriging/variogramas con gstools — enfoque geoestadístico
                        NO usado en NN.ipynb, que resuelve el cruce espacial con
                        intersección exacta de polígonos de cobertura)
```

## Cómo usar esta guía

1. Si vas a **retomar trabajo en `NN.ipynb`**, empieza por `NN_notebook.md` para saber qué
   sección corresponde a qué año/experimento y qué variables de entrada necesita.
2. Si necesitas **una versión más limpia** de una sección de `NN.ipynb` (clustering,
   correlaciones, detección de anomalías, filtrado de glint, series de tiempo), revisa
   `pipeline_stages.md`: casi siempre existe una variante más pulida en `data_analysis/`
   o `time series/` que puede reemplazar el bloque equivalente del notebook principal.
3. Antes de "limpiar" o consolidar código, revisa
   `redundancias_e_inconsistencias.md` para no perder de vista qué versión es la vigente.

## Notas de entorno (ya documentadas en el repo, resumidas aquí)

- Gestor de entorno: `uv` (`uv sync --group notebooks --group analysis` para trabajar con
  `NN.ipynb`; añade `--group surface` para `surface_retrieve/`).
- Datos pesados (CSV, shapefiles, GRIB, `.pth`, resultados) están excluidos por
  `.gitignore` y deben obtenerse/conservarse localmente (fuente: IDEAM para cobertura de
  tierra, Google Earth Engine para TROPOMI).
- `NN.ipynb` no es un pipeline ejecutable con "Run All": mezcla bloques por año
  (2018–2024) con cargas comentadas y rutas heredadas de Google Colab
  (`/content/drive/Shareddrives/...`) y una ruta absoluta `/home/hernan/...` sin portar.
  Ver `scripts_2026/Scripts/README.md` para el detalle de qué activar según el año a analizar.
