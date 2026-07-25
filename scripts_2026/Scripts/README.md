# `NN.ipynb`: entorno, datos y ejecución

`NN.ipynb` es un cuaderno exploratorio con varias etapas de preparación,
cruce espacial, análisis estadístico y redes neuronales. No es actualmente un
pipeline que se pueda ejecutar completo con **Run All**: conserva bloques para
años y experimentos distintos, algunas cargas están comentadas y varias celdas
dependen del estado producido por ejecuciones anteriores.

## Entorno versionado

Desde la raíz del repositorio:

```bash
uv sync --group notebooks --group analysis
uv run jupyter lab scripts_2026/Scripts/NN.ipynb
```

Las dependencias principales del cuaderno están declaradas en
`pyproject.toml` y fijadas en `uv.lock`. Algunas secciones históricas o
comentadas mencionan paquetes no declarados (`deepl`, `polars`, TensorFlow y
utilidades de Google Colab); no son parte del entorno reproducible actual.

El bloque histórico de traducción requiere la variable de entorno
`DEEPL_AUTH_KEY` y el paquete `deepl`. No se deben guardar claves en el
notebook ni en Git.

## Datos que no se versionan

Los CSV, shapefiles, GeoPackages, geodatabases y salidas generadas están
excluidos por `.gitignore` debido a su tamaño. Deben obtenerse de la fuente
institucional del proyecto y mantenerse localmente. La estructura local usada
por el trabajo actual es:

```text
scripts_2026/
├── Datos_a_05-2026/
│   ├── colombia_prom_2019.csv
│   ├── colombia_prom_2020.csv
│   ├── colombia_prom_2021.csv
│   ├── colombia_prom_2022.csv
│   ├── colombia_prom_2023.csv
│   └── colombia_corr_*.csv
└── Scripts/
    ├── NN.ipynb
    ├── Cobertura_de_la_Tierra_100K_Periodo_2018/
    ├── Cobertura_de_la_tierra_100K_Periodo_2020_limite_administrativo/
    ├── Cobertura_tierra_100K_periodo_2022_limite_administrativo/
    └── Cobertura_Tierra_100K_Periodo_2024_limite_administrativo/
```

No todas las etapas necesitan todos los archivos. Para el bloque que está
editado actualmente para 2022–2023 se requieren, como mínimo:

- la cobertura de tierra de 2022
  (`ECOSISTEMAS_18062025.gpkg` o su geodatabase equivalente);
- `colombia_prom_2022.csv`;
- `colombia_prom_2023.csv`.

Los bloques comparativos requieren además las coberturas de 2018, 2020 y 2024,
y los CSV `colombia_corr_*` de los años analizados.

Los metadatos incluidos en las entregas locales identifican al IDEAM como
productor y al Geoportal institucional (`http://www.ideam.gov.co/geoportal`)
como canal de consulta y descarga. Si una versión no está publicada allí, los
metadatos indican solicitarla al IDEAM. Conviene registrar aquí el enlace
exacto, la fecha de descarga y el checksum de cada entrega cuando se consolide
el flujo reproducible.

## Rutas que hay que adaptar antes de ejecutar

El cuaderno todavía contiene rutas heredadas de Google Colab
(`/content/drive/Shareddrives/PIGCC/...`) y una ruta absoluta
`/home/hernan/...`. Antes de ejecutar una etapa, sustituya sus cargas y salidas
por rutas relativas a esta carpeta. Una base portable es:

```python
from pathlib import Path

NOTEBOOK_DIR = Path.cwd()
DATA_DIR = NOTEBOOK_DIR.parent / "Datos_a_05-2026"

df_s_2022 = pd.read_csv(DATA_DIR / "colombia_prom_2022.csv")
df_s_2023 = pd.read_csv(DATA_DIR / "colombia_prom_2023.csv")
```

Si Jupyter se inició con otro directorio de trabajo, ajuste `NOTEBOOK_DIR` a
la carpeta que contiene `NN.ipynb`.

## Estado conocido del inicio del cuaderno

La versión actual carga `dfg_2018`, pero deja comentadas las cargas de
`dfg_2022` y `dfg_2024` aunque celdas posteriores usan esas variables. También
usa `df_s_2026` después de dejar comentada su carga. Por tanto, seleccione el
año que va a analizar, active su carga con una ruta local y ejecute solamente
el bloque correspondiente. Convertir el cuaderno completo en un pipeline
lineal requerirá separar y ordenar esos experimentos.
