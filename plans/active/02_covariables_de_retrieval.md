# Plan 02 — Covariables de retrieval: albedo SWIR, aerosoles, geometría e incertidumbre

**Estado:** ⬜ pendiente · **Depende de:** 01 · **Desbloquea:** 03 · **Esfuerzo:** 2–3 días

## 1. Objetivo

Separar lo que en el efecto de la cobertura es **emisión de CH₄** de lo que es **sesgo del
retrieval que cambia con la superficie**. Este es el plan que protege la rama causal (§4):
a diferencia de la altitud, estas covariables **no se cancelan al diferenciar**, porque
cambiar la cobertura cambia la reflectancia de la superficie.

## 2. Justificación científica

TROPOMI recupera XCH₄ a partir de la absorción en el SWIR (2.3 µm). El algoritmo operacional
tiene un sesgo residual conocido que depende del **albedo SWIR de la superficie** y de la
carga y altura de **aerosoles**; el producto `bias_corrected` aplica una corrección a
posteriori que, en el producto operacional, es función del albedo retrievado. La
corrección reduce el sesgo pero no lo elimina, y su forma ha cambiado entre versiones del
producto (ver Lorente et al., AMT 2021, y las notas de versión del producto L2 CH₄).

Por qué esto es una amenaza directa a §4: bosque denso es oscuro en SWIR; pasto, suelo
desnudo y cultivo son más claros. Una transición bosque→pasto cambia el albedo del píxel,
y si queda sesgo residual con el albedo, el modelo lo leerá como cambio de CH₄. El signo
del artefacto no se conoce a priori (depende de la versión del producto), así que hay que
medirlo.

Además, el recolector ya descarga covariables de calidad que hoy no se usan:
`aerosol_optical_depth`, `aerosol_height`, los cuatro ángulos y la incertidumbre por
sondeo. Y la diferencia entre `CH4_column_volume_mixing_ratio_dry_air` y
`..._bias_corrected` es, por construcción, **la corrección aplicada**, es decir un proxy
gratuito del albedo retrievado. Agotar eso antes de descargar nada.

## 3. Insumos

| Insumo | Dónde |
|---|---|
| Bandas por sondeo: CH₄ sin corregir, corregido, incertidumbre, AOD, altura de aerosol, ángulos | `CH4_glintfiltered_colombia_2019-2026.csv` (verificar que trae las bandas auxiliares; si no, `data_collection/outputs/s5p_ch4/*.parquet`) |
| Albedo de superficie externo | `MODIS/061/MCD43A3`, bandas `Albedo_BSA_Band7` / `Albedo_WSA_Band7` (2.1 µm, 500 m, diario) + banda de calidad |
| Versión del producto L2 | Columna de metadatos del recolector (`STRING_METADATA_COLUMNS`) |

## 4. Pasos

### Paso 1 — Proxy interno del albedo (medio día)

1. Calcular por sondeo `correccion = dry_air − bias_corrected`. Describirla: media, rango,
   histograma, mapa de su media por píxel.
2. Comprobar que es una función suave de la superficie y no ruido: su media por píxel
   debe ser espacialmente coherente (bosque ≠ sabana) y estable entre años.
3. Tabular la versión del producto por fecha: si cambia dentro de 2019–2025 (lo hace),
   la corrección cambia de forma y hay que incluir **efectos fijos de versión** o, al menos,
   verificar que las medias bienales no mezclan versiones de manera desbalanceada entre
   clases de cobertura.

### Paso 2 — Albedo externo (1 día)

1. `collect_covariates_gee.py --layer albedo_swir`: media anual y mensual de
   `Albedo_BSA_Band7` con máscara de calidad, a 0.01° y 0.06°. Salida:
   `covariables/estaticas_0p01.parquet` (+`albedo_swir_2022`, `albedo_swir_2024`) y
   `covariables/mensuales/albedo_swir_0p01.parquet`.
2. Validar el proxy del paso 1 contra MODIS: correlación por píxel entre `correccion`
   media y `albedo_swir`. Si r > 0.7 el proxy vale como sustituto; si no, se usa MODIS.
3. Comprobar que el albedo **cambia** con el cambio de cobertura: en el panel bienal,
   regresar Δalbedo sobre Δcomposición. Si Δalbedo no responde a Δcobertura, el riesgo de
   este plan es menor de lo temido y se documenta.

### Paso 3 — Modelos con covariables de retrieval (1 día)

Especificaciones, acumulativas, sobre §3 (ya con elevación del plan 01) y §4 agrupado:

| Esp. | Añade |
|---|---|
| R0 | nada (referencia) |
| R1 | albedo SWIR (lineal y spline) |
| R2 | + AOD, altura de aerosol |
| R3 | + ángulo cenital solar y del sensor (la huella y la masa de aire cambian con ellos) |
| R4 | + efectos fijos de versión de producto (solo a nivel de sondeo; en medias bienales, como fracción de sondeos por versión) |

Para cada una: tabla de trayectoria de las clases interpretables y la correlación con R0.

### Paso 4 — Ponderación por incertidumbre (medio día)

La incertidumbre por sondeo es heterogénea (albedo bajo, aerosol, ángulos). Repetir el
agrupado de §4 con **mínimos cuadrados ponderados** por 1/σ² agregado al píxel-bienio
(σ² media de los sondeos / n). Es una robustez, no la especificación principal: la
incertidumbre reportada del producto es teórica y puede estar correlacionada con la
superficie.

### Paso 5 — Prueba de falsación específica

Si el efecto bosque→pasto de §4 fuera artefacto de albedo, debería **desaparecer al
controlar por Δalbedo** y **reaparecer con el mismo signo al regresar Δalbedo sobre
Δcobertura**. Reportar las dos regresiones juntas; es el argumento más convincente para
un revisor que conozca TROPOMI.

## 5. Criterio de cierre

- [ ] Proxy `correccion` caracterizado y validado (o descartado) contra MODIS, con r reportado.
- [ ] Versiones del producto en el periodo tabuladas y su balance entre clases verificado.
- [ ] Tabla R0–R4 para §3 y §4, guardada en `resultados/*_p02.csv`.
- [ ] Respuesta explícita: *¿el efecto por cambio de cobertura sobrevive al control por albedo y aerosoles?*
      Se considera respondida si se reporta el cambio relativo del coeficiente de las
      clases interpretables entre R0 y R2 (sobrevive si < 30 % y el signo se mantiene).
- [ ] Decisión sobre qué covariables de retrieval entran en la especificación canónica → plan 03.

## 6. Qué va al artículo

- Métodos: párrafo sobre sesgo residual por albedo/aerosol y cómo se controló.
- Suplemento: tabla R0–R4 y la regresión Δalbedo ~ Δcobertura.

## 7. Riesgos

- MCD43A3 banda 7 es 2.1 µm, no 2.3 µm; es un proxy espectral cercano, no el mismo albedo.
  Decirlo.
- Sobrecontrol: el albedo es consecuencia del cambio de cobertura. Si se controla por él
  se está quitando parte del efecto causal (un *collider*/mediador). Por eso la
  especificación canónica debe reportar **ambas** versiones, con y sin albedo, y el texto
  explicar que la verdad está entre las dos.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
- 2026-08-24 — Recolector del paso 2 listo: `--layer albedo_swir` descarga MCD43A3 banda 7 BSA/WSA con máscara `Mandatory_Quality ≤ 0`, medias mensuales y anuales a 0.01°/0.06°, y escribe `mensuales/albedo_swir_0p01.parquet` + columnas `albedo_swir_2022/2024` en las estáticas. Falta ejecutar la descarga (autenticación GEE).
