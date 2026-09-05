# Plan 01 — Topografía y física de la columna: elevación, presión superficial y rugosidad

**Estado:** 🔄 en curso · **Depende de:** — · **Desbloquea:** 02, 03 · **Esfuerzo:** 2–3 días
**Prioridad:** máxima. Es el plan con mayor relación resultado/costo de toda la secuencia.

## 1. Objetivo

Cuantificar cuánto del efecto transversal de la cobertura (§3) es en realidad altitud, e
incorporar la elevación —y sus derivados: presión superficial y rugosidad del terreno—
como covariable canónica de ambas ramas.

## 2. Justificación científica (para el texto del artículo)

XCH₄ es la fracción molar media de la **columna** de aire seco, no una concentración
superficial. La estratosfera tiene mucho menos CH₄ que la troposfera (el CH₄ se oxida
arriba de la tropopausa). Sobre terreno alto la columna troposférica es más corta y la
fracción estratosférica pesa más, de modo que **XCH₄ disminuye con la elevación aunque no
cambie ninguna emisión**. Con tropopausa tropical a ~100 hPa y un déficit estratosférico
medio de ~250 ppb, pasar de 1 000 a 700 hPa de presión superficial (0 → ~3 000 m) baja el
XCH₄ en ~10 ppb sólo por ese mecanismo; a eso se suma que a mayor altitud se pierde la
capa límite, que es la parte enriquecida de la columna. En los Andes colombianos eso son
10–20 ppb, es decir **un orden de magnitud más que el efecto por clase de cobertura (~1 ppb)**.

El problema es que la cobertura CORINE está estratificada por altitud: bosque denso en
Amazonía y Pacífico (bajo), páramo y cultivos transitorios en la cordillera (alto),
herbazales en Orinoquía (bajo). En §3 eso se confunde con el efecto de la clase. En §4 la
altitud se cancela al diferenciar, y esa es una explicación candidata —y verificable— de
por qué las magnitudes de §4 son ~0.6× las de §3.

Segundo efecto, de calidad de dato: el retrieval de TROPOMI usa un DEM para fijar la
presión superficial del píxel. En terreno rugoso (gran varianza de elevación dentro de la
huella de 7 km) ese supuesto es malo y el retrieval pierde calidad. La desviación típica
de la elevación dentro de la huella es una covariable de calidad, análoga a `fraccion_agua_abierta`.

## 3. Insumos

| Insumo | Dónde | Notas |
|---|---|---|
| DEM | `COPERNICUS/DEM/GLO30` (30 m) en GEE; alternativa `USGS/SRTMGL1_003` | GLO30 es más reciente y mejor en zonas de nube; SRTM es lo que usan muchos retrievals |
| Presión superficial | `ECMWF/ERA5_LAND/MONTHLY_AGGR` banda `surface_pressure` (11 km) | Se usa como chequeo: debe ser función casi determinista de la elevación |
| Malla de píxeles | Coordenadas únicas de `CH4_glintfiltered_colombia_2019-2026.csv` | Es la unión de todas las mallas anuales (~700 k puntos) |
| §3 y §4 | `ajustar_transversal`, `ajustar_causal` en `NN_areas_igac.ipynb` | No se modifican; se envuelven |

## 4. Pasos

### Paso 1 — Infraestructura de covariables (medio día)

1. Crear `data_collection/collect_covariates_gee.py` siguiendo el patrón de
   `collect_gee_colombia.py` (argumentos, reintentos, `_collection_config.json`), con un
   modo `--layer dem` que:
   - reduce GLO30 a una malla de 0.01° alineada con la de S5P (`bin_spatial` con origen
     en 50.0 / −120.0, ver §4.3 del notebook) con **tres reductores**: media, desviación
     típica y mínimo/máximo;
   - repite a 0.06° (7 km, huella real) para `elev_std_7km`;
   - exporta un GeoTIFF recortado a Colombia por reductor.
2. Muestrear los GeoTIFF en los centros de píxel de la malla de CH₄ (`rasterio`, añadir
   con `uv add rasterio`) y escribir `covariables/estaticas_0p01.parquet` con columnas
   `elev_m`, `elev_std_1km`, `elev_std_7km`, `elev_min_7km`, `elev_max_7km` y el JSON hermano.
3. Crear `unir_covariables(df, nombres)` en una celda de §1 (o en `common/`) que une por
   (`longitude`, `latitude`) con redondeo explícito a 5 decimales y **falla** si queda
   algún píxel sin covariable.
4. Crear `knowledge/covariables.md` con la ficha de estas columnas.

### Paso 2 — Verificación del mecanismo físico (medio día)

Antes de meter la elevación en el modelo de cobertura, medirla sola:

1. Regresión `XCH₄ ~ elev_m` por año (2022, 2023) sobre `df_valido`, con errores por
   bloque de 0.5°. Reportar la pendiente en ppb/km.
2. Lo mismo con `surface_pressure` (ERA5-Land) como regresor: la pendiente en ppb/hPa
   debe ser consistente con la de elevación vía la hipsométrica (~−0.11 hPa/m).
3. Gráfico de dispersión XCH₄ vs. elevación con la media por bin de 250 m y la curva
   teórica del déficit estratosférico superpuesta. Es una figura del artículo (suplemento).
4. Comprobar no linealidad: ajustar además `elev_m + elev_m²` y un spline; si la
   curvatura es relevante, la covariable entra como spline, no como lineal.

**Resultado esperado:** pendiente negativa, entre −3 y −8 ppb/km. Si sale positiva o
nula, algo está mal en la unión de coordenadas o en la máscara: detenerse y revisar.

### Paso 3 — §3 con control de elevación (medio día)

1. Envolver `ajustar_transversal` en una versión que acepte `covariables_extra` (lista de
   columnas) y las añada al diseño **después** de la composición. No cambiar la función
   original hasta el plan 03.
2. Correr tres especificaciones por año: (a) sin elevación [actual], (b) + `elev_m`,
   (c) + spline de `elev_m` + `elev_std_7km`.
3. Tabla de trayectoria del coeficiente: para las 11 clases interpretables, efecto por
   +10 pp en (a), (b), (c), y el valor de §4 agrupado como referencia.
4. Guardar en `resultados/transversal_nivel3_cobertura_2022_p01.csv`.

### Paso 4 — §4 con rugosidad y chequeo de cancelación (medio día)

1. En §4 la elevación se cancela por construcción; verificarlo empíricamente: añadir
   `elev_m` al agrupado y comprobar que el coeficiente es ~0 y que los demás no se mueven.
   Si se mueve, hay un componente estacional (tropopausa × altitud) que no se cancela →
   documentar y pasar la interacción al plan 06.
2. Añadir `elev_std_7km` como covariable de calidad y, por separado, como criterio de
   exclusión (p. ej. > 500 m): reportar si los errores estándar bajan al excluir terreno
   muy rugoso. Si bajan de forma apreciable, proponer el umbral para la máscara de calidad
   (decisión formal en el plan 03).

### Paso 5 — Documentar

Celda markdown nueva al final de §3, "3.1 Control por elevación", con la tabla del paso 3
y dos frases de interpretación. Ficha en `knowledge/covariables.md`.

## 5. Criterio de cierre

- [ ] `estaticas_0p01.parquet` cubre el 100 % de los píxeles de la malla de CH₄ (0 NaN).
- [ ] Pendiente XCH₄ ~ elevación reportada con IC, por año, en ppb/km.
- [ ] Tabla de trayectoria (a)/(b)/(c) para las 11 clases interpretables, guardada en `resultados/`.
- [ ] Respuesta explícita a la pregunta: *¿la atenuación 0.6× entre §3 y §4 es altitud?*
      Se considera respondida si, con elevación, la mediana de |β₃/β₄| sobre las clases
      interpretables se mueve hacia 1 (sí) o no se mueve (no). Ambas respuestas cierran el plan.
- [ ] Coeficiente de `elev_m` en §4 ≈ 0 verificado (o interacción estacional documentada).

## 6. Decisiones que este plan deja tomadas

- Si `elev_std_7km` mejora la precisión en §4: umbral propuesto para la máscara → plan 03.
- Forma funcional de la elevación (lineal vs. spline) → se usa en todos los planes posteriores.

## 7. Qué va al artículo

- Figura (suplemento): XCH₄ vs. elevación con curva teórica.
- Tabla: trayectoria del coeficiente con y sin elevación.
- Un párrafo de métodos sobre por qué una columna exige controlar por presión superficial.

## 8. Riesgos

- Desalineación de mallas (GLO30 remuestreado vs. centros de píxel S5P): verificar con un
  transecto de la cordillera que el perfil de elevación tiene sentido.
- La elevación es casi colineal con temperatura media (−6.5 K/km): **no** meter las dos
  como efectos principales más adelante (plan 06).

## 9. Registro de avance

- 2026-08-23 — Plan creado.
- 2026-08-24 — Paso 1 implementado: `data_collection/collect_covariates_gee.py` (capas `dem` y `albedo_swir`, GeoTIFF por reductor a 0.01°/0.06° con `computePixels`, reanudable), `unir_covariables` en `common/covariables.py`, ficha en `knowledge/covariables.md`, 17 tests. Malla CH₄ cacheada: 652 425 píxeles, 0 desalineados. Pendiente la descarga real: requiere `earthengine authenticate` en la VPS.
