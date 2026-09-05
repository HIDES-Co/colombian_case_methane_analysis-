# Plan 05 — Hidrología e inundación: agua en el suelo, lluvia y extensión inundada como drivers de los humedales

**Estado:** ⬜ pendiente · **Depende de:** 03 (y 06 para la humedad del suelo de ERA5-Land, opcional) · **Desbloquea:** 09 · **Esfuerzo:** 3–4 días

## 1. Objetivo

Controlar la **variabilidad interanual hidrológica** —la que §4 no cancela— y, a la vez,
convertir el efecto de los humedales de un número fijo en una **función del estado
hídrico**, que es como lo entiende la literatura de emisiones de humedales.

## 2. Justificación científica

Los humedales son la mayor fuente natural de CH₄ y en estos datos los píxeles de humedal
están +13 ppb sobre el fondo seco. Su emisión depende de dos cosas: **extensión inundada**
(área anóxica) y **temperatura del suelo** (tasa de metanogénesis). La extensión inundada en
Colombia cambia drásticamente entre años: La Niña 2020–2023 (tres años consecutivos)
inundó La Mojana, el bajo Magdalena y la Orinoquía; El Niño 2023–2024 produjo sequía e
incendios. Esa variabilidad:

- es **temporal**, así que §4 no la quita;
- es **regional**, así que el bloque×par del plan 03 la quita en parte, pero no la parte
  que interactúa con la composición del píxel (un píxel con 40 % de humedal responde a la
  inundación más que su vecino con 0 %);
- coincide en el tiempo con los pares de cobertura: el par 2020→2022 es La Niña pura, el
  2022→2024 incluye la transición a El Niño.

Sin esto, un cambio de cobertura hacia "áreas húmedas" en un par lluvioso se leerá como
efecto de la clase cuando es efecto del año. Y al revés.

Por qué **no** humedad relativa del aire: no gobierna la emisión; lo que la gobierna es el
agua en el suelo. Por qué la lluvia de ERA5 no es la mejor opción: el reanálisis reproduce
mal la convección en terreno complejo; CHIRPS está calibrado con estaciones.

## 3. Insumos

| Variable | Fuente | Resolución | Cobertura temporal | Notas |
|---|---|---|---|---|
| Humedad superficial y de zona radicular del suelo | `NASA/SMAP/SPL4SMGP/007` (`sm_surface`, `sm_rootzone`) | 11 km, 3-horaria | 2015-03– | Producto de asimilación L4; coherente en el tiempo |
| Humedad del suelo (alternativa) | ERA5-Land `volumetric_soil_water_layer_1..4` | 11 km, horaria/mensual | 1950– | Llega con el plan 06 |
| Precipitación | `UCSB-CHG/CHIRPS/DAILY` | 0.05°, diaria | 1981– | Acumulados mensuales y anomalías |
| Agua superficial mensual | `JRC/GSW1_4/MonthlyHistory` | 30 m, mensual | **hasta 2021-12** | Cubre el par 2018→2020 y el inicio del 2020→2022 |
| Agua superficial 2022– | Sentinel-1 GRD (`COPERNICUS/S1_GRD`), umbral VV | 10 m | 2014– | Más trabajo; solo si GSW no basta |
| Índice ENSO | ONI (NOAA CPC), tabla mensual | — | — | Contexto y variable de par |

## 4. Pasos

### Paso 1 — Capas mensuales (1.5 días)

1. `collect_covariates_gee.py --layer smap`: media mensual de `sm_surface` y
   `sm_rootzone` a 0.01° y 0.06° con **identificador de celda fuente** (plan 03, paso 6).
2. `--layer chirps`: acumulado mensual y anomalía respecto a la climatología 1991–2020
   del mismo mes (en mm y en percentil).
3. `--layer gsw`: fracción de la celda clasificada como agua en `MonthlyHistory` por mes
   hasta 2021-12, y fracción de "agua estacional" vs "permanente".
4. Derivados por píxel-bienio: media de humedad del suelo, anomalía de lluvia del bienio,
   `fraccion_inundada_max` y `fraccion_inundada_media` (solo hasta 2021), y por sondeo:
   humedad del suelo del mes del sondeo.
5. Sanidad: la serie nacional de anomalía de lluvia debe mostrar La Niña 2020–23 y El Niño
   2023–24; SMAP y CHIRPS deben correlacionar en el tiempo por celda.

### Paso 2 — Estado hídrico como covariable de par (medio día)

Sobre la canónica de §4: añadir Δ(humedad del suelo del bienio) y Δ(anomalía de lluvia)
como covariables. Reportar cuánto cambian los coeficientes de las clases de humedal
(`4.1.1`, `4.1.2`, `4.1.3`) y de arroz/cultivos inundables. Con bloque×par activo, la
parte regional ya está absorbida; lo que quede es la parte local.

### Paso 3 — Interacción humedal × estado hídrico (1 día)

Especificación con interacción: `ΔCH₄ = ... + β_h·Δhumedal + γ·(humedal_media × Δhumedad_suelo) + ...`.
Esto convierte el efecto del humedal en `β_h + γ·estado`, y permite decir "un humedal
emite X ppb más en un año de La Niña que en uno de El Niño". Hacerlo también en §3 (con
el nivel de humedad del año, no el Δ): allí la interacción es espacial y temporal a la vez.

### Paso 4 — Inundación real vs. clase de cobertura (medio día)

Para los pares cubiertos por GSW (hasta 2021): comparar la fracción de "áreas húmedas"
del IGAC con la fracción realmente inundada del mes. Si la clase IGAC es estática y la
inundación varía, la covariable relevante es la inundación, y la clase es solo su
potencial. Reportar la correlación y el rango.

### Paso 5 — Documentar

Celda "4.5 Estado hídrico" con las tablas; ficha en `knowledge/covariables.md`.

## 5. Criterio de cierre

- [ ] Capas mensuales SMAP, CHIRPS y GSW en `covariables/mensuales/` con JSON de procedencia
      y celda fuente.
- [ ] Coeficientes de las clases de humedal con y sin control hídrico, en
      `resultados/causal_*_p05.csv`.
- [ ] Interacción humedal × humedad del suelo estimada con IC, y traducida a "ppb por
      humedal en año húmedo vs. seco".
- [ ] Decisión: ¿entra el estado hídrico en la canónica como covariable, como interacción,
      o se deja como heterogeneidad? Escribirla en `ESPECIFICACION_CANONICA`.
- [ ] Decisión sobre Sentinel-1: solo si GSW deja sin cubrir algo que el artículo necesita.

## 6. Qué va al artículo

- Resultado: efecto de humedales modulado por ENSO (figura: coeficiente del humedal por
  par con el ONI del par superpuesto).
- Métodos: justificación de SMAP/CHIRPS sobre ERA5 para lluvia y humedad del suelo.

## 7. Riesgos

- SMAP L4 es un producto de asimilación con modelo; no es una observación pura. Decirlo.
- GSW termina en 2021: el par 2022→2024 queda sin inundación observada. Sentinel-1 es la
  salida, pero cuesta días; decidir por necesidad, no por completitud.
- Pseudo-replicación: SMAP y ERA5 a 11 km. Aplicar las reglas del plan 03.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
