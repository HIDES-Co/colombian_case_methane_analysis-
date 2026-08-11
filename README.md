# Colombian Case Methane Analysis

Herramientas y cuadernos para recolectar, analizar y visualizar mediciones de metano atmosférico en Colombia.

## Entorno con uv

El repositorio usa [uv](https://docs.astral.sh/uv/) como único gestor de Python, dependencias y entorno virtual. La versión de desarrollo es Python 3.11 y está declarada en `.python-version`.

Instala `uv` y crea el entorno correspondiente según el análisis:

```bash
uv sync # solo base
uv sync --all-groups
```

Los grupos opcionales son:

- `notebooks`: JupyterLab y kernel de Python.
- `analysis`: estadística, clustering, autoencoders y visualización avanzada.
- `surface`: lectura de perfiles atmosféricos en GRIB mediante `pygrib`.
- `dev`: pruebas y linting.

Por ejemplo, para trabajar solamente con notebooks y análisis:

```bash
uv sync --group notebooks --group analysis
```

Ejecuta scripts dentro del entorno con `uv run`:

```bash
uv run python all_data_plotting/plotting.py
uv run jupyter lab
uv run ruff check .
```

Tras cambiar `pyproject.toml`, actualiza el lockfile con `uv lock`. El archivo `uv.lock` debe versionarse para que todos usen las mismas versiones resueltas.

### Trabajando desde una VPS (sin navegador local)

Si este repositorio se ejecuta en una VPS (como es el caso actual), `uv run jupyter lab`
por sí solo intentará abrir un navegador en la propia máquina remota, lo cual falla porque
no hay entorno gráfico. Hay dos formas prácticas de trabajar:

**JupyterLab remoto + túnel SSH (recomendada para notebooks pesados como `NN.ipynb`)**

En la VPS:

```bash
uv run jupyter lab --no-browser --ip=0.0.0.0 --port=8888 --allow-root
```

y, desde tu máquina local, un túnel SSH hacia ese puerto:

```bash
ssh -N -L 8888:localhost:8888 -l root -p 22 194.163.183.88
```

## Datos y credenciales

Los archivos grandes de satélite, GRIB, ráster, resultados generados, modelos y credenciales están excluidos mediante `.gitignore`. Cada persona debe conservarlos localmente y configurar sus credenciales de Google Earth Engine antes de ejecutar los flujos que usan `ee`.
