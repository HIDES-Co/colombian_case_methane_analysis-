# Redundancias e inconsistencias detectadas

Lista de puntos donde la misma lógica existe en más de un lugar con distinto grado de
madurez, o donde hay decisiones no reconciliadas entre notebooks. Útil como punto de
partida si se decide consolidar el repo en un pipeline único.

1. **Cruce espacial CH4 × cobertura de tierra y filtrado de "glint"** están reimplementados
   al menos 4 veces: `NN.ipynb` (con dos versiones internas, una vectorizada con
   `ThreadPoolExecutor`/`ProcessPoolExecutor` comentada y otra con loops simples),
   `time series/dataFiltering.ipynb`, y `data_analysis/correlations.ipynb`. No existe una
   función compartida en `common/` para esto — sería el primer candidato a extraer.

2. **Autoencoder de detección de anomalías**: arquitectura idéntica en `NN.ipynb` y en
   `data_analysis/deteccion_anomalias.ipynb`, pero el preprocesamiento de datos diverge
   (`RobustScaler`/`MinMaxScaler` en `data_analysis/`, normalización manual en `NN.ipynb`).
   No está documentado cuál es la versión vigente/correcta.

3. **Clustering K-means**: `NN.ipynb` usa `alpha_star = 3` fijo sin justificación, mientras
   `data_analysis/clusters.ipynb` sí calcula k óptimo (elbow, silhouette,
   Calinski-Harabasz, Davies-Bouldin). El bloque de `NN.ipynb` debería actualizarse para
   usar ese resultado en vez de repetir el análisis con un valor fijo.

4. **Dos enfoques no reconciliados para relacionar CH4 con el espacio**:
   kriging/variograma (`common/satelite.py`, usado solo por `all_data_plotting/plotting.py`)
   vs. intersección de polígonos de cobertura de tierra (`NN.ipynb` y todo
   `data_analysis/`). No hay comparación de cuál es más apropiado para qué pregunta.

5. **Portabilidad de rutas desigual**: `NN.ipynb` todavía tiene rutas de Google Colab
   (`/content/drive/Shareddrives/...`) y una ruta absoluta `/home/hernan/...`, mientras que
   `data_analysis/` y `time series/` ya usan rutas relativas basadas en
   `os.getcwd()`/`parent_dir`. Sugiere que la portabilidad se abordó primero fuera del
   notebook principal y nunca se retrofiteó allí.

6. **`temp_correlations_clusters_dataAnalysis.ipynb`** (raíz del repo) probablemente es un
   snapshot intermedio de `NN.ipynb` ya superado por la separación en `data_analysis/`.
   Candidato a archivar o eliminar una vez se confirme que todo su contenido relevante fue
   migrado (no se hizo esa confirmación exhaustiva en este análisis).

7. **Identificador de proyecto de Earth Engine inconsistente**: `common/satelite.py` usa
   `ee-jolejua`, mientras que `data_collection/getCSV.ipynb` usa `ee-hides`.

8. **Modelos `.pth` sin registro de procedencia**: `data_analysis/*.pth` (`best_model.pth`,
   `mymodel_prueba.pth`, `mymodel_prueba2.pth`, `mymodel_prueba_corrected_filtered.pth`,
   `mymodel_prueba_v2.pth`) no tienen metadata de qué notebook/preprocesamiento/hiperparámetros
   los generó más allá del nombre del archivo.
