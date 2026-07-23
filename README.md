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

## Datos y credenciales

Los archivos grandes de satélite, GRIB, ráster, resultados generados, modelos y credenciales están excluidos mediante `.gitignore`. Cada persona debe conservarlos localmente y configurar sus credenciales de Google Earth Engine antes de ejecutar los flujos que usan `ee`.
