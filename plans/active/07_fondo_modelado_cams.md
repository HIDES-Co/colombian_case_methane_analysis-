# Plan 07 — Fondo modelado (CAMS): trabajar con el realce ΔXCH₄ = TROPOMI − modelo

**Estado:** ⬜ pendiente · **Depende de:** 01 · **Desbloquea:** 09, 10 · **Esfuerzo:** 4–6 días
**Relación con el repositorio:** reutiliza `surface_retrieve/` (lectura de GRIB CAMS EGG4 y `vertical_methane_profile.py`), que hoy no está integrado en el flujo principal.

## 1. Objetivo

Sustituir la variable respuesta XCH₄ por el **realce local respecto a un fondo modelado**,
de modo que el gradiente latitudinal, el ciclo estacional, la contribución estratosférica
y el transporte de gran escala salgan del residuo de una sola vez, con un dato
independiente de la cobertura.

## 2. Justificación científica

Colombia va de 4° S a 12° N: la ITCZ la cruza dos veces al año y con ella el gradiente
interhemisférico de CH₄ (el hemisferio norte tiene más). Eso introduce en XCH₄ una
estructura latitud × mes de varios ppb que (a) en §3 se confunde con la distribución
latitudinal de las coberturas y (b) en §4 interactúa con qué meses se observó cada
píxel. La forma estándar en la literatura de TROPOMI para aislar fuentes locales es
restar un modelo de transporte (CAMS, GEOS-Chem) y trabajar con el realce.

Frente a la alternativa barata —una superficie suave en (lat, lon, mes)— el modelo tiene
una ventaja decisiva: **es independiente del mapa de coberturas**. Una superficie suave
absorbe "Amazonía = bosque" y se lleva parte del efecto; el modelo no sabe nada de la
composición del píxel (más allá de los inventarios gruesos que usa, ver riesgos).

El plan 01 controla la altitud con el DEM; este plan hace lo mismo de forma física (el
modelo ya integra la columna con su perfil vertical) y además quita lo que el DEM no
puede: lo que varía en el tiempo.

## 3. Insumos

| Producto | Cobertura | Resolución | Notas |
|---|---|---|---|
| CAMS global greenhouse gas reanalysis (EGG4) | 2003–2020 | 0.75°, 3-horaria, 25 niveles | Ya se lee en `surface_retrieve/EGG4_handling.ipynb`. Cubre solo el bienio 2018 (2019) y parte del 2020 |
| CAMS global inversion-optimised greenhouse gas fluxes and concentrations (CH₄) | 1990–presente (latencia ~1–2 años) | ~2° × 3°, mensual/instantánea | Continuidad para 2021–2025; gruesa pero suficiente como fondo |
| CAMS global atmospheric composition forecasts (CH₄) | 2019–presente | 0.4°, 3-horaria | Más fina; es un pronóstico, no reanálisis |

Verificar en el Atmosphere Data Store la disponibilidad y latencia **antes** de elegir.
La decisión se toma por cobertura temporal completa 2019–2025 con un solo producto, no
por resolución: mezclar dos productos introduce un escalón en el fondo justo en un par.

## 4. Pasos

### Paso 1 — Elección y descarga (1 día)

1. Inventario de productos CAMS con CH₄ en 3D o como columna para 2019-01 a 2025-12 sobre
   la caja de Colombia (−82 a −66, −5 a 14). Tabla con resolución, frecuencia, latencia.
2. Descargar el elegido (perfil en niveles de presión o modelo, presión superficial,
   vapor de agua si se necesita para columna seca) vía la API del ADS. Script en
   `surface_retrieve/descargar_cams.py`, reanudable por mes.

### Paso 2 — Columna seca modelada (1–2 días)

1. A partir del perfil: XCH₄_modelo = ∫ CH₄(p) dp_seco / ∫ dp_seco, con la presión
   superficial **del modelo** (no del DEM: el modelo es consistente consigo mismo).
   Adaptar `vertical_methane_profile.py`.
2. Idealmente aplicar el núcleo de promediado (*averaging kernel*) de TROPOMI y su perfil
   a priori; el producto L3 de GEE **no los trae**. Documentar que se usa la columna sin AK
   y estimar el error con un caso de prueba (AK de TROPOMI en SWIR es cercano a 1 en la
   troposfera; el error es de pocos ppb y sobre todo en la estratosfera).
3. Interpolar XCH₄_modelo a la hora y posición de cada sondeo (o, para §4, media mensual
   por píxel). Guardar en `covariables/mensuales/xch4_cams_0p01.parquet` con celda fuente.

### Paso 3 — Validación del fondo (medio día)

1. Media nacional TROPOMI vs. modelo por mes: deben seguir la misma tendencia y estación;
   un sesgo medio constante es aceptable (se va con el intercepto), una deriva no.
2. Gradiente latitudinal por mes en ambos: deben coincidir en forma.
3. Regresión XCH₄_TROPOMI ~ XCH₄_modelo por bienio: pendiente ≈ 1. Si está lejos, el
   modelo no es un buen fondo para este uso y se registra.

### Paso 4 — Modelos con realce (1 día)

1. §3 con respuesta ΔXCH₄ = TROPOMI − modelo, con y sin elevación. Si el modelo hace su
   trabajo, el coeficiente de elevación debe acercarse a 0 (ya está en el fondo).
2. §4 con Δ(realce) en vez de ΔXCH₄. El efecto fijo de par debe bajar hacia 0 (la
   tendencia global ya está en el modelo) y los coeficientes de cobertura deben ser
   estables respecto a la canónica.
3. Tabla de trayectoria y correlación de coeficientes con la canónica.

### Paso 5 — Documentar

Celda "3.2 / 4.6 Realce respecto al fondo CAMS"; ficha en `knowledge/covariables.md`;
integrar `surface_retrieve/` en `knowledge/pipeline_stages.md` como etapa del flujo vigente.

## 5. Criterio de cierre

- [ ] Producto CAMS elegido con cobertura 2019–2025 continua; descarga reanudable.
- [ ] XCH₄_modelo por píxel-mes y por sondeo, validado (tendencia, estación, gradiente,
      pendiente ≈ 1).
- [ ] §3 y §4 con realce; trayectoria de coeficientes en `resultados/*_p07.csv`.
- [ ] Decisión: la respuesta canónica es XCH₄ con covariables (plan 01) o el realce.
      Criterio: la que deje menor autocorrelación espacial residual (rango del variograma
      del plan 03, paso 2) con coeficientes equivalentes.

## 6. Qué va al artículo

- Métodos: definición del realce y del fondo. Es lo que esperan los revisores del área.
- Suplemento: validación TROPOMI vs. CAMS sobre Colombia (figura de series y gradiente).

## 7. Riesgos

- El modelo usa inventarios (EDGAR, humedales de modelos) como flujos a priori: contiene
  un mapa grueso de fuentes. A 0.75–2° no puede "saber" la composición de un píxel de
  7 km, pero sí la de una región; parte del efecto regional de las coberturas puede
  quedar en el fondo. Es la razón para reportar **ambas** respuestas.
- La inversión optimizada asimila observaciones de satélite (GOSAT, posiblemente
  TROPOMI): hay circularidad parcial. Verificar qué observaciones asimila el producto
  elegido y decirlo.
- Sin AK, el realce tiene un sesgo dependiente de la altitud; el plan 01 ya lo cubre.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
