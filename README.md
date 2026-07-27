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

**Opción A — JupyterLab remoto + túnel SSH (recomendada para notebooks pesados como `NN.ipynb`)**

En la VPS:

```bash
uv run jupyter lab --no-browser --ip=0.0.0.0 --port=8888
```

Copia el token que imprime la consola (o la URL completa `http://127.0.0.1:8888/lab?token=...`).
Desde tu máquina local, abre un túnel SSH hacia ese puerto:

```bash
ssh -N -L 8888:localhost:8888 usuario@ip-de-la-vps
```

Con el túnel activo, abre `http://localhost:8888/lab?token=...` en el navegador de tu
máquina local — el tráfico viaja cifrado por SSH y JupyterLab nunca intenta abrir un
navegador en la VPS.

**Opción B — Editor remoto (VS Code / Cursor Remote-SSH, JetBrains Gateway)**

Conéctate a la VPS con la extensión Remote-SSH de tu editor y abre el `.ipynb` directamente
ahí; el editor ejecuta las celdas contra el kernel remoto sin necesitar túnel manual ni
navegador aparte. Recuerda seleccionar el intérprete de `.venv` (creado por `uv sync`) como
kernel.

**Opción C — Ejecución sin interfaz, solo para validar que corre**

Para correr un notebook de punta a punta sin abrir ninguna interfaz (útil para notebooks ya
lineales, no para `NN.ipynb` mientras siga siendo exploratorio):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace ruta/al_notebook.ipynb
```

## Datos y credenciales

Los archivos grandes de satélite, GRIB, ráster, resultados generados, modelos y credenciales están excluidos mediante `.gitignore`. Cada persona debe conservarlos localmente y configurar sus credenciales de Google Earth Engine antes de ejecutar los flujos que usan `ee`.
