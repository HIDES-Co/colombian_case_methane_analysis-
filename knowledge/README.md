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
- [`glint_y_calidad_del_dato.md`](./glint_y_calidad_del_dato.md) — si el *sun glint*
  compromete el XCH₄ sobre zonas inundadas (caso La Mojana): geometría de S5P sobre
  Colombia, evidencia empírica, criterio de la máscara de calidad y qué falta para
  defenderlo en publicación.

## Notebook vigente: `scripts_2026/Scripts/NN_areas_igac.ipynb`

`NN.ipynb` es el monolito histórico. El trabajo activo está en `NN_areas_igac.ipynb`, que
reorganiza el flujo en secciones numeradas y tiene **dos ramas de análisis** que no hay que
confundir:

| | §3 transversal | §4 causal |
|---|---|---|
| insumo | `colombia_corr_metano_2022_2023_cobertura_2022.csv` | `panel_bienal_cobertura_multianual.csv` |
| cobertura | **una** capa (2022) para los dos años de CH₄ | **su propia** capa por periodo (2018/2020/2022/2024) |
| CH₄ | media anual simple | media bienal con meses equiponderados |
| identifica | asociación en el espacio | efecto del cambio en el tiempo |

La rama causal empareja cada capa del IGAC con el bienio de CH₄ que le corresponde
(2018↔2019, 2020↔2020-21, 2022↔2022-23, 2024↔2024-25) porque las coberturas oficiales
salen cada dos años. El bienio 2018 tiene un solo año: el producto L3 de Sentinel-5P en
Earth Engine arranca el 2019-02-08.

Las columnas dummy de cobertura las fija un **catálogo canónico de 166 clases**, no la capa
de cada año; sin eso `pd.get_dummies` emite solo las clases presentes en cada capa y el
panel multi-año se alinea con NaN en silencio.

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
