# Plan maestro — De correlación a inferencia robusta: covariables y diseño estadístico

**Estado:** 🔄 en curso · **Creado:** 2026-08-23 · **Notebook eje:** `scripts_2026/Scripts/NN_areas_igac.ipynb` (§3 y §4)

## 1. Por qué existe este plan

El notebook ya estima el efecto de la cobertura de la tierra sobre el XCH₄ de TROPOMI por
dos vías independientes —transversal (§3) y primeras diferencias sobre el panel bienal
(§4)— y ambas coinciden en el signo de 11 clases. Eso es un resultado, pero para un
artículo no basta: un revisor preguntará (a) si el efecto transversal es cobertura o
altitud, (b) si el efecto por cambio es emisión o un artefacto del retrieval que cambia
junto con la cobertura (albedo), (c) si lo que se atribuye a deforestación es combustión
transitoria, y (d) cómo se controló la variabilidad interanual de lluvia e inundación
(La Niña 2020–23, El Niño 2023–24) que coincide espacial y temporalmente con la frontera
de cambio de cobertura.

El análisis de 2026-08-23 (ver §5) concluyó que **la covariable más importante que falta
no es climatológica sino topográfica**, seguida de los confusores de retrieval, y que
entre las climáticas dominan el agua en el suelo y el fuego sobre temperatura y humedad.
Este plan maestro convierte esa evaluación en una secuencia de metas con criterio de
cierre medible.

## 2. Principio rector

Cada covariable cumple un papel distinto en cada rama, y el plan se ordena por eso:

| Tipo de variable | En §3 (transversal) | En §4 (diferencias) |
|---|---|---|
| Invariante en el tiempo (altitud, fuentes fijas, latitud) | confusor fuerte | se cancela al diferenciar |
| Varía en el tiempo (ENSO, inundación, fuego, viento) | poco | **único confusor que §4 no quita** |
| Artefacto de retrieval que cambia con la cobertura (albedo SWIR, aerosoles) | confusor | **no se cancela: cambia con el tratamiento** |

Regla práctica que aplica a todos los planes: **antes de descargar un dato externo,
agotar lo que ya está en el repositorio** (diferencia entre bandas corregida y sin
corregir, ángulos, AOD, `n_meses`, los vecinos espaciales como control).

## 3. Secuencia y dependencias

```
FASE A · Base física y diseño (secuencial, obligatoria)
  01 Topografía y columna ──► 02 Covariables de retrieval ──► 03 Escala y diseño estadístico
                                                                        │
FASE B · Confusores que varían en el tiempo (paralelizable tras 03)     │
  04 Fuego y quema ◄────────────────────────────────────────────────────┤
  05 Hidrología e inundación ◄──────────────────────────────────────────┤
  06 Meteorología ERA5 (viento, temperatura, nubosidad) ◄───────────────┘

FASE C · Fondo y fuentes (paralelizable, independiente de B)
  07 Fondo modelado CAMS
  08 Fuentes antrópicas y control positivo

FASE D · Modelo integrado y síntesis (requiere A, B, C)
  09 Modelo de dos vías a nivel de sondeo + estudio de eventos
  10 Robustez (DML), tabla de sensibilidad y material del artículo
```

| # | Plan | Depende de | Desbloquea | Esfuerzo (días-persona) |
|---|---|---|---|---|
| 01 | [Topografía y columna](01_topografia_y_columna.md) | — | 02, 03 | 2–3 |
| 02 | [Covariables de retrieval](02_covariables_de_retrieval.md) | 01 | 03 | 2–3 |
| 03 | [Escala y diseño estadístico](03_escala_y_diseno_estadistico.md) | 01, 02 | 04–09 | 4–5 |
| 04 | [Fuego y quema](04_fuego_y_quema.md) | 03 | 09 | 2–3 |
| 05 | [Hidrología e inundación](05_hidrologia_e_inundacion.md) | 03 | 09 | 3–4 |
| 06 | [Meteorología ERA5](06_meteorologia_era5.md) | 03 | 05 (viento/suelo), 09 | 2–3 (nivel A) + 3–4 (nivel B, condicional) |
| 07 | [Fondo modelado CAMS](07_fondo_modelado_cams.md) | 01 | 09, 10 | 4–6 |
| 08 | [Fuentes antrópicas y control positivo](08_fuentes_antropicas_y_control_positivo.md) | 01 | 09, 10 | 2–3 |
| 09 | [Modelo de dos vías a nivel de sondeo](09_modelo_dos_vias_nivel_sondeo.md) | 03–08 | 10 | 5–7 |
| 10 | [Robustez y material del artículo](10_robustez_y_material_articulo.md) | 01–09 | artículo | 4–5 |

Total: del orden de 7–9 semanas de trabajo efectivo si se ejecuta en serie; las fases B y
C se pueden solapar. Los planes 01, 02 y 04 son los de mayor relación resultado/costo y
cada uno produce por sí solo un resultado publicable.

## 4. Convenciones de todos los planes

- **Un plan = una meta cerrable.** Cada plan tiene objetivo, justificación científica,
  insumos, pasos con entregable, criterio de cierre medible y lo que aporta al artículo.
- **Estado** en la cabecera: ⬜ pendiente · 🔄 en curso · ✅ cerrado · ⛔ bloqueado (decir por qué).
- **Cierre.** Al cumplir el criterio de cierre se añade la sección "Cierre" al final
  (fecha, resultado numérico, decisión tomada) y el archivo se mueve a `plans/done/`.
  Un plan cuyo resultado refuta la hipótesis también se cierra: la refutación es un resultado.
- **Registro de avance** al final de cada plan: fecha + una línea. Es la memoria del
  proyecto; lo que no esté ahí no pasó.
- **Nada se modifica en §3/§4 sin pasar por el plan 03.** Hasta entonces las nuevas
  covariables se evalúan en celdas nuevas que leen los mismos insumos y escriben en
  `Datos_a_05-2026/resultados/` con sufijo del plan (`_p01`, `_p02`, ...).
- **Capas de covariables** viven en `scripts_2026/Datos_a_05-2026/covariables/`:
  - `estaticas_0p01.parquet` — una fila por píxel (`longitude`, `latitude`) de la malla
    de CH₄ (unión de coordenadas de `CH4_glintfiltered_colombia_2019-2026.csv`).
  - `mensuales/<variable>_0p01.parquet` — una fila por (`longitude`, `latitude`, `year`, `month`).
  - Cada archivo lleva un `.json` hermano con fuente, resolución nativa, fecha de
    descarga, método de remuestreo y licencia. **La resolución nativa se conserva como
    columna** (`<variable>_res_nativa_m`) y, para capas gruesas, el identificador de la
    celda fuente, para poder agrupar errores por ella (ver plan 03).
  - Una sola función de unión, `unir_covariables(df, nombres)`, en una celda de §1
    o en `common/`; nunca un `merge` a mano dentro de un análisis.
- **Descarga desde GEE**: se extiende el patrón de `data_collection/collect_gee_colombia.py`
  con un segundo script `collect_covariates_gee.py` (plan 01 lo crea). Para capas
  estáticas y mensuales la ruta más barata y reproducible es exportar un GeoTIFF a 0.01°
  recortado a Colombia y muestrearlo localmente en los centros de píxel; no hace falta
  enviar 700 k puntos a Earth Engine.
- **Documentación**: cada plan cerrado actualiza `knowledge/covariables.md` (lo crea el
  plan 01) con una ficha por variable.

## 5. Resumen del análisis que origina el plan (2026-08-23)

Prioridad de covariables, de mayor a menor relevancia para este problema:

1. **Elevación / presión superficial** (DEM). XCH₄ es una columna: a mayor altitud, la
   fracción estratosférica pobre en CH₄ pesa más y XCH₄ *baja* sin que cambie ninguna
   emisión. Orden de magnitud 3–5 ppb/km sólo por ese mecanismo; entre 0 y 3 000 m son
   10–20 ppb, **10× el efecto de cobertura (~1 ppb)**, y la cobertura CORINE está
   estratificada por altitud. Confusor dominante de §3 y candidato principal a explicar la
   atenuación 0.6× entre §3 y §4.
2. **Fondo modelado (CAMS)** → trabajar con ΔXCH₄ = TROPOMI − modelo. Quita de una vez el
   gradiente latitudinal (la ITCZ cruza Colombia), el ciclo estacional, la estratosfera y
   el transporte de gran escala.
3. **Albedo SWIR y aerosoles.** Sesgo residual del retrieval; bosque→pasto cambia el
   albedo, luego **no se cancela en §4**. Proxy gratuito: diferencia entre las bandas
   `..._dry_air` y `..._bias_corrected`.
4. **Agua en el suelo / inundación / lluvia.** Driver real de los humedales, varía con ENSO.
5. **Fuego.** La deforestación colombiana es por quema (ene–mar), justo cuando TROPOMI
   observa más. Discrimina combustión transitoria de emisión estable.
6. **Viento.** Orienta el núcleo de §4.3 y actúa como ventilación. La altura de capa
   límite importa poco para columnas.
7. **Temperatura.** Sólo como interacción humedal × temperatura; colineal con altitud.
8. **Fuentes antrópicas fijas** (EDGAR, O&G, carbón, luces nocturnas). Confusor en §3,
   exclusión/heterogeneidad en §4 y **control positivo** de la sensibilidad del dato.
9. Nubosidad como modelo de selección del muestreo. 10. NDVI/EVI: baja prioridad.

### Técnica estadística: dónde se ejecuta cada punto

Los cinco cambios de técnica propuestos en el análisis entran todos en la secuencia.
Esta tabla es la trazabilidad:

| # | Técnica propuesta | Qué resuelve | Plan y paso |
|---|---|---|---|
| 1 | **Efectos fijos bloque × par** (diferenciación espacial) | Confusores temporales regionales —ENSO, tasa de crecimiento, transporte, meses observados— sin nombrarlos | 03 · paso 4; generalizado a región × mes en 09 · paso 2 |
| 2 | **Modelo de dos vías a nivel de sondeo** (píxel + región×mes) + estudio de eventos | Usa los 12 M de sondeos, admite covariables en su tiempo nativo, elimina el equiponderado manual; trayectoria antes/después de perder bosque | 09 · pasos 1–5 |
| 3 | **Errores estándar de Conley** (HAC espacial) | Dependencia espacial sin fronteras arbitrarias de bloque; cierra el pendiente de §4.2 | 03 · pasos 2–3 |
| 4 | **Reglas de pseudo-replicación** para covariables gruesas (ERA5, SMAP, EDGAR) | Que 120 celdas con el mismo valor de 11 km no cuenten como 120 observaciones | 03 · paso 6; aplicado en 05, 06, 07, 08 |
| 5 | **Double machine learning** + bosque causal | Robustez a la forma funcional de los confusores; heterogeneidad del efecto | 10 · paso 1 |
| — | Agregación a la huella real (0.06°) y núcleo de exposición (§4.3) | Deshace el refinamiento artificial de la malla; estima la huella atmosférica efectiva | 03 · pasos 1 y 5; anisotrópico en 06 · paso 3 |
| — | Ponderación por probabilidad inversa del muestreo (nubosidad) | Selección de cielo despejado correlacionada con la cobertura | 06 · paso 6 |
| — | Estimador robusto a tratamiento escalonado (Sun–Abraham / Callaway–Sant'Anna) | Sesgo del TWFE ingenuo con efectos heterogéneos | 09 · paso 5 |
| — | Specification curve y tabla de sensibilidad única | Muestra qué coeficientes son estables en todas las especificaciones | 10 · paso 2 |

## 6. Riesgos transversales

| Riesgo | Mitigación |
|---|---|
| Pseudo-replicación: ERA5/SMAP (11–28 km) repiten el mismo valor en cientos de celdas de 0.01° | Conservar celda fuente; agrupar errores al menos a esa rejilla; agregar a 0.06° (plan 03) |
| Sobreajuste al añadir muchas covariables a un efecto de ~1 ppb | Una covariable a la vez, reportar la trayectoria del coeficiente, DML al final (plan 10) |
| Covariable que absorbe el tratamiento (una superficie espacial suave absorbe "Amazonía = bosque") | Preferir fondo modelado independiente (plan 07) a polinomios en lat/lon |
| Cuello de botella de potencia: muestreo temporal del CH₄ | Plan 09 usa los 12 M de sondeos en vez de medias bienales |
| Coste de GEE / cuota | Exportar rásteres, no muestrear puntos; un GeoTIFF por capa-mes |

## 7. Fuente única de planificación

`plans/active/` es el **único** lugar donde se planifica. No se mantienen planes
paralelos en otros directorios: el antiguo `data_collection/METEOROLOGY_PLAN.md` se
absorbió en el plan 06 y se eliminó el 2026-08-23. Si surge una idea que no cabe en un
plan existente, se añade como paso o como plan nuevo aquí, con su prioridad por impacto,
nunca como documento suelto.

## 8. Registro de avance

- 2026-08-23 — Plan maestro y planes 01–10 creados a partir del análisis de covariables.
- 2026-08-23 — `METEOROLOGY_PLAN.md` absorbido en el plan 06 (niveles A/B por impacto) y eliminado.
