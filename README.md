# Colombian Case Methane Analysis

Herramientas y cuadernos para recolectar, analizar y visualizar mediciones de metano atmosférico en Colombia.

---

## Flujo de ejecución en VPS

Instrucciones para configurar el entorno, gestionar procesos con `tmux`, ejecutar Jupyter Lab en el VPS y utilizar Antigravity CLI (`agy`).

---

### 1. Configuración del entorno con uv

El repositorio utiliza [uv](https://docs.astral.sh/uv/) como gestor de Python y dependencias (Python 3.11 declarado en `.python-version`).

1. Instalar `uv` (si no está disponible):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.local/bin/env
   ```

2. Sincronizar dependencias:
   ```bash
   # Instalar dependencias base y todos los grupos
   uv sync --all-groups
   ```
   *O instalar solo grupos específicos:*
   ```bash
   uv sync --group notebooks --group analysis
   ```

3. Registrar el kernel para Jupyter:
   ```bash
   uv run python -m ipykernel install --user --name colombian-methane --display-name "Python (Colombian Methane)"
   ```

---

### 2. Ejecutar Jupyter Lab con tmux

1. Crear una sesión de `tmux`:
   ```bash
   tmux new -s jupyter
   ```

2. Iniciar el servidor con el script de inicio (genera token y muestra la URL local):
   ```bash
   ./start_jupyter.sh
   ```
   *(Opcional: puedes pasar un puerto específico, ej. `./start_jupyter.sh 8889`)*

3. Desacoplar la sesión:
   - Presiona `Ctrl + b` y luego `d`.

---

### 3. Conexión local mediante túnel SSH

Desde tu máquina local (Asgurate que estas en local!!!), redirige el puerto del VPS:

```bash
ssh -N -L 8888:localhost:8888 -l root -p 22 <IP_DEL_VPS>
```

Abre en tu navegador:
```
http://localhost:8888
```
Ingresa el token si es requerido.

---

### 4. Uso de Antigravity CLI (agy)

1. Iniciar una sesión persistente para el CLI:
   ```bash
   tmux new -s agy
   ```

2. Ejecutar el asistente:
   ```bash
   agy
   ```

3. Desacoplar con `Ctrl + b` y `d`. Para retomar la sesión:
   ```bash
   tmux attach -t agy
   ```

---

## Referencia de comandos

### Comandos de tmux

| Acción | Comando |
| :--- | :--- |
| Crear sesión | `tmux new -s <nombre>` |
| Listar sesiones | `tmux ls` |
| Reconectar a sesión | `tmux attach -t <nombre>` |
| Desacoplar sesión activa | `Ctrl + b` luego `d` |
| Eliminar sesión | `tmux kill-session -t <nombre>` |

### Comandos comunes con uv

```bash
# Ejecutar scripts
uv run python all_data_plotting/plotting.py

# Linters y pruebas
uv run ruff check .
uv run pytest

# Actualizar dependencias resueltas
uv lock
```

### Grupos de dependencias

- `notebooks`: JupyterLab, ipykernel e inspector de variables.
- `analysis`: Modelado, clustering, PyTorch, Scikit-learn, Pingouin y visualización.
- `surface`: Lectura de archivos GRIB (`pygrib`, `basemap`).
- `dev`: Pruebas (`pytest`) y análisis estático (`ruff`).

---

## Datos y credenciales

Los archivos de datos satelitales, GRIB, ráster y credenciales están excluidos en `.gitignore`.

Para autenticar Google Earth Engine:
```bash
uv run python -c "import ee; ee.Authenticate()"
```
