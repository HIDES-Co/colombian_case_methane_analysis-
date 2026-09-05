# Plan 06 — Meteorología ERA5: viento para el núcleo a barlovento, humedad del suelo, nubosidad como selección, temperatura como interacción

**Estado:** ⬜ pendiente · **Depende de:** 03 · **Desbloquea:** 05 (humedad del suelo alternativa), 09 · **Esfuerzo:** 2–3 días el nivel A; +3–4 días el nivel B (condicional)

Este plan **absorbe y reemplaza** el antiguo `data_collection/METEOROLOGY_PLAN.md`
(versión preliminar, eliminada el 2026-08-23). Todo lo que de él seguía siendo útil está
aquí; lo que no, se descartó con la justificación de §2.

## 1. Objetivo

Incorporar la meteorología con el papel que realmente tiene para una **columna** de CH₄:
el viento define de dónde viene el aire que ve el píxel (y por tanto la exposición
correcta a la cobertura); la humedad del suelo modula la emisión de humedales; la
nubosidad explica por qué unos píxeles se observan en unos meses y otros en otros; la
temperatura modula la emisión pero es casi colineal con la altitud. La temperatura y la
humedad del aire **no** son covariables principales en este problema.

## 2. Priorización por impacto

| Nivel | Variable | Fuente | Impacto en la investigación | Por qué |
|---|---|---|---|---|
| **A** | `u/v_component_of_wind_10m` (y 100 m o 850 hPa en los Andes) | ERA5-Land / ERA5 mensual | **alto** | Núcleo a barlovento (§4.3) y ventilación: convierte la exposición a cobertura en la exposición física correcta y estima la huella atmosférica |
| **A** | `volumetric_soil_water_layer_1` | ERA5-Land mensual | **alto** | Driver de humedales; alternativa o complemento a SMAP (plan 05) |
| **A** | `total_cloud_cover` | ERA5 mensual | **medio-alto** | Modelo de selección del muestreo de cielo despejado, correlacionado con la cobertura |
| **A** | `temperature_2m` | ERA5-Land mensual | medio | Solo como interacción humedal × temperatura; no como efecto principal (colineal con `elev_m`, plan 01) |
| **A** | `surface_pressure` | ERA5-Land mensual | ya usada en plan 01 | Chequeo físico de la elevación |
| **B** | Todo lo anterior **por sondeo, a la hora de la órbita** | ERA5-Land / ERA5 horario | medio, **condicional** | Solo lo necesita el modelo a nivel de sondeo (plan 09, ventilación instantánea). Es la descarga más cara del proyecto |
| descartado | `dewpoint_temperature_2m` → humedad relativa | — | bajo | No gobierna emisiones; el retrieval ya trata el vapor de agua. Se conserva como banda opcional del perfil, no se analiza |
| descartado | `total_precipitation_hourly` | — | bajo | CHIRPS es mejor en Colombia (plan 05). Se conserva como opcional |
| descartado | `boundary_layer_height` | ERA5 (28 km) | **bajo** | Las columnas son insensibles a la distribución vertical; la BLH importa para concentración superficial, no para XCH₄. Además es la variable más gruesa |
| descartado | MODIS LST (`MODIS/061/MOD11A1`) como sustituto de `temperature_2m` | — | — | Mide temperatura radiométrica de superficie, con otra hora de paso y solo en cielo despejado; no sustituye la temperatura del aire |

Regla: **el nivel A basta para §3/§4 y para cerrar los planes 05 y 09 en su forma
básica.** El nivel B se ejecuta solo si el plan 09 decide que la ventilación instantánea
por sondeo cambia resultados en una prueba piloto de un mes (paso 5).

## 3. Insumos

| Insumo | Fuente | Resolución | Notas |
|---|---|---|---|
| Agregados mensuales (nivel A) | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | 11.1 km, mensual | `u10`, `v10`, `t2m`, `swvl1`, `sp` |
| Nubosidad mensual (nivel A) | `ECMWF/ERA5/MONTHLY` | 27.8 km, mensual | `total_cloud_cover` |
| Horario (nivel B) | `ECMWF/ERA5_LAND/HOURLY`, `ECMWF/ERA5/HOURLY` | 11.1 / 27.8 km, horaria | Emparejado a `system:time_start` de cada órbita S5P |
| Hora de cada sondeo | columna `date` (UTC) de los parquet del recolector | — | `date_colombia` es solo informativa: **la unión se hace en UTC** |

ERA5-Land representa una rejilla de modelo, no estaciones: en valles y montañas
colombianas viento y temperatura pierden variación local. Se dice en el artículo.

Referencias: [ERA5-Land Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY) ·
[ERA5 Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_HOURLY) ·
[ERA5-Land Daily Aggregated](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR) ·
[MODIS MOD11A1](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1).
Licencia y atribución Copernicus C3S/ECMWF en todo producto derivado.

## 4. Convenciones de procedencia (aplican a A y B)

Heredadas del plan preliminar y consistentes con las reglas de covariables gruesas del
plan 03 (paso 6). Toda fila enriquecida con ERA5 lleva:

| Columna | Contenido |
|---|---|
| `era5_source` | colección GEE de origen |
| `era5_grid_x`, `era5_grid_y` | índice de la celda fuente en la proyección nativa |
| `era5_source_longitude`, `era5_source_latitude` | centro de la celda fuente |
| `era5_native_scale_m` | 11 132 (ERA5-Land) o 27 830 (ERA5) |
| solo nivel B: `era5_time` (UTC), `era5_time_offset_minutes` (con signo), `era5_within_tolerance` | emparejamiento temporal |

- **Unión espacial: vecino más cercano en la proyección nativa de ERA5.** Sin
  interpolación bilineal por defecto. Nunca se describe el resultado como un dato de 1.1 km.
- **Las bandas originales se conservan siempre** (K, Pa, m/s, m). Las conversiones se
  calculan localmente, se documentan y no sustituyen el valor fuente:
  `t2m_c = t2m − 273.15`, `wind_speed_10m = sqrt(u² + v²)`, `wind_dir_10m` meteorológica
  (de dónde sopla), `sp_hpa = sp / 100`. Si se conserva la precipitación: `mm = m × 1000`,
  usando `total_precipitation_hourly` y no la acumulación reiniciada a medianoche; los
  pequeños negativos del empaquetado GRIB se dejan en el dato fuente y cualquier corrección
  es explícita. Si se deriva humedad relativa (opcional): validar contra una
  implementación de referencia y limitar a 0–100 % solo el derivado.
- Comprobación obligatoria de pseudo-replicación: todos los píxeles S5P con el mismo
  (`era5_grid_x`, `era5_grid_y`, tiempo) comparten exactamente los mismos valores fuente
  (regresión auxiliar con R² = 1). Los errores se agrupan al menos a la celda ERA5.

## 5. Pasos

### Paso 1 — Nivel A: agregados mensuales (1 día) · impacto alto

`collect_covariates_gee.py --layer era5_monthly`: por mes 2019-01 → 2025-12, las bandas
de nivel A remuestreadas a 0.01° y 0.06° por vecino más cercano, con las columnas de
procedencia de §4. Salida `covariables/mensuales/era5_0p01.parquet` + JSON hermano.
Derivar `wind_speed_10m`, `wind_dir_10m` y la **rosa de vientos climatológica por
píxel y mes** (para el paso 2).

Controles: conversión K→°C en casos conocidos; velocidad del viento; comparar puntos de
ciudades a distinta elevación (Bogotá 2 600 m, Medellín 1 500 m, Barranquilla 0 m,
Leticia 100 m) con la climatología conocida; reportar faltantes ERA5 por separado de los
faltantes S5P.

### Paso 2 — Núcleo a barlovento (1 día) · impacto alto

Extender `suavizar_exposicion` (plan 03, paso 5) a un núcleo **anisotrópico**: elipse
orientada según la dirección climatológica del viento del mes (o del bienio), con
semieje mayor `h_along` a barlovento y `h_across` perpendicular. Barrer `h_along`
manteniendo `h_across` fijo y comparar con el isotrópico por validación espacial. Si el
anisotrópico mejora, el `h_along` estimado es la distancia de transporte efectiva y se
contrasta con viento × tiempo de mezcla (2–5 m/s × pocas horas ≈ 30–70 km). En los Andes
probar también el viento a 100 m o en 850 hPa de ERA5: el de 10 m es poco fiable allí.

### Paso 3 — Ventilación y temperatura como interacciones (medio día) · impacto medio

1. Velocidad del viento del bienio como covariable y como interacción con la
   composición: el realce de columna de una fuente local escala con emisión/viento, así
   que se espera que los coeficientes de clases emisoras sean mayores con viento bajo. Es
   un chequeo de plausibilidad física del efecto.
2. `humedal × t2m_anomalía` en §4 (y `humedal × t2m` en §3, reportado con y sin
   elevación para mostrar la colinealidad). No meter `t2m` como efecto principal junto a
   `elev_m`.
3. `swvl1` pasa al plan 05 como alternativa/complemento de SMAP.

### Paso 4 — Selección del muestreo por nubosidad (1 día) · impacto medio-alto

El píxel se observa cuando está despejado; la nubosidad depende de la cobertura (bosque
más nuboso) y de la estación. Dos tratamientos:

1. **Descriptivo**: para cada clase de cobertura, distribución de meses observados y
   `total_cloud_cover` medio del mes; mostrar el sesgo.
2. **Ponderación por probabilidad inversa**: modelar P(observado | píxel, mes) con la
   nubosidad y ponderar los sondeos por 1/P al construir la media bienal. Comparar los
   coeficientes con y sin ponderación. Si cambian poco, el equiponderado de meses de §1.2
   ya bastaba y se dice; si cambian, se adopta la ponderación.

### Paso 5 — Nivel B, condicional: recolector horario por sondeo (3–4 días) · impacto medio

Se ejecuta **solo** si el plan 09 lo pide tras un piloto de un mes. Especificación
(heredada del plan preliminar, vigente):

1. Añadir `--meteorology none|era5-land|era5-combined` a `collect_gee_colombia.py`,
   con `none` por defecto. Perfil `era5-land`: `temperature_2m`, `u/v_component_of_wind_10m`,
   `surface_pressure`, `volumetric_soil_water_layer_1` (+ opcionales `dewpoint_temperature_2m`,
   `total_precipitation_hourly`). Perfil `era5-combined`: añade `total_cloud_cover` de ERA5.
2. Dentro de cada trabajo por órbita S5P, resolver la imagen ERA5 horaria que minimiza
   |Δt| respecto a `system:time_start`, con **tolerancia máxima de 90 minutos**; registrar
   `era5_time`, `era5_time_offset_minutes` y `era5_within_tolerance`. Comparación siempre
   en instantes UTC; nunca con la fecha local como clave.
3. Añadir las bandas ERA5 y las coordenadas de su celda al `ee.Image` **antes** del único
   `Image.sample()`, y aplicar a toda la pila la máscara de la banda CH₄ corregida: no se
   descargan píxeles donde S5P no tiene observación. No se descargan las 24 h de ERA5
   sobre Colombia; solo la hora necesaria por órbita.
4. Conservar paginación, paralelismo, reintentos y escritura atómica del recolector.
   Escribir en un **directorio distinto** (esquema y `_collection_config.json`
   incompatibles con el dataset CH₄ base), registrando colección, bandas, regla temporal,
   tolerancia y método espacial.
5. Pruebas de rendimiento sobre un mismo mes antes de la serie completa:

   | Corrida | Propósito |
   |---|---|
   | Solo CH₄ | línea base de tiempo, EECU y tamaño |
   | CH₄ + ERA5-Land | coste del perfil de nivel A |
   | CH₄ + ERA5-Land + ERA5 | coste de la nubosidad |

   Registrar imágenes/minuto, filas/segundo, bytes Parquet por fila, reintentos, fallos y
   EECU si Cloud Monitoring lo expone.
6. Aceptación: cero cambios en filas, coordenadas y CH₄ frente a la corrida base del
   mismo periodo; |Δt| ≤ 90 min en todas las filas no nulas; celda ERA5 identificable en
   cada fila; reanudación sin duplicados tras una interrupción; pruebas unitarias de
   conversión y selección temporal en `tests/`; smoke test en vivo sobre una órbita
   comparado a mano con el catálogo GEE.

## 6. Criterio de cierre

- [ ] Nivel A: capas mensuales ERA5 en `covariables/mensuales/` con columnas de
      procedencia y JSON; controles del paso 1 pasados.
- [ ] Núcleo anisotrópico vs. isotrópico comparado; `h_along` reportado y contrastado con
      la referencia física.
- [ ] Interacciones viento y temperatura estimadas, en `resultados/causal_*_p06.csv`.
- [ ] Sesgo de selección por nubosidad descrito y ponderación evaluada; decisión escrita
      en `ESPECIFICACION_CANONICA`.
- [ ] Decisión explícita sobre el nivel B: *se ejecuta / no se ejecuta* y por qué (resultado
      del piloto del plan 09). Si se ejecuta: aceptación del paso 5.6 cumplida.
- [ ] `data_collection/README.md` actualizado con lo implementado.

## 7. Qué va al artículo

- Métodos: exposición a barlovento y estimación de la huella atmosférica efectiva.
- Suplemento: sesgo de muestreo por nubosidad y su efecto en los coeficientes; nota sobre
  la resolución y naturaleza de modelo de ERA5-Land.

## 8. Riesgos

- ERA5-Land pierde la circulación valle-montaña; mitigación: viento a 100 m / 850 hPa.
- Pseudo-replicación (11–28 km sobre celdas de 0.01°): reglas del plan 03 y la
  comprobación de R² = 1 de §4.
- Coste de GEE del recolector horario: por eso es condicional y va después del nivel A.
- ERA5-Land publica incidencias conocidas en bandas de evaporación; no forman parte del
  perfil.

## 9. Registro de avance

- 2026-08-23 — Plan creado.
- 2026-08-23 — Absorbe `data_collection/METEOROLOGY_PLAN.md` (eliminado); reordenado por
  impacto en niveles A (mensual, obligatorio) y B (horario por sondeo, condicional).
