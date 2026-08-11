# Glint, agua superficial y defensa de la calidad del dato

Análisis del 2026-07-28 sobre si el *sun glint* compromete las mediciones de XCH₄ en las
zonas inundadas de Colombia, con La Mojana como caso crítico. Documenta la física, la
geometría calculada para Colombia, la evidencia empírica extraída de los datos del
proyecto, y qué falta para cerrar el argumento en una publicación.

Contexto de código: la máscara de calidad y sus umbrales viven en el bloque de
alistamiento de `scripts_2026/Scripts/NN_areas_igac.ipynb` (celdas 20–22). Ver también
[`redundancias_e_inconsistencias.md`](./redundancias_e_inconsistencias.md) punto 1, que
ya señalaba el filtrado de "glint" reimplementado en cuatro lugares.

---

## 1. Qué es el glint y por qué importa aquí

El *sun glint* es reflexión **especular** de la luz solar sobre una superficie de agua
lisa. Requiere dos condiciones simultáneas:

1. **Geometría**: ángulo cenital de observación ≈ ángulo cenital solar (VZA ≈ SZA) y
   azimut relativo ≈ 180°.
2. **Superficie especular**: agua abierta y suficientemente lisa. La vegetación emergente
   rompe la condición: devuelve reflectancia difusa, no especular.

Importa porque fuera de glint el agua es casi negra en SWIR (2.3 µm), donde se recupera
el CH₄: la señal es tan baja que la recuperación falla o queda con `qa_value` bajo. En
glint la radiancia es alta y sí hay recuperación, pero con sesgos conocidos (aerosoles,
rugosidad de la superficie / velocidad del viento). Por eso el producto operacional de
TROPOMI recupera sobre tierra, y sobre océano esencialmente solo en modo glint.

## 2. Linaje histórico en este proyecto

La exclusión de agua y humedales **era** el filtro de glint. El comentario original está
en el propio notebook:

```python
encoded_df45 = encoded_df[(encoded_df['Leyenda_1_4. Wetlands']>0)
                        + (encoded_df['Leyenda_1_5. Water bodies']>0)]
# tabla para eliminar el glint en la plataforma continental
```

De ahí sale el **nombre** de `Datos_a_05-2026/CH4_glintfiltered_colombia_2019-2026.csv`.

> **Corrección (2026-07-28).** Una versión anterior de este documento afirmaba que ese
> archivo tenía el filtro aplicado, "verificado: cero filas con fracción de agua o humedal
> > 0". Ese conteo era **vacuo**. Al recontarlo sobre las 12,011,475 filas, las columnas
> `Leyenda_1_4. Áreas húmedas` y `Leyenda_1_5. Superficies de agua` tienen **cero valores
> no nulos**: están enteramente vacías, así que ninguna fila podía superar el umbral. El
> archivo **no está filtrado por cobertura**; solo tiene un join de cobertura sin poblar.

Lo que realmente es: la **serie por sondeo completa**, con agua y humedales incluidos. Sus
coordenadas únicas por año coinciden al dígito con los `colombia_prom_<year>.csv`
(176,492 / 307,155 / 321,434 / 359,869 / 471,586 para 2019–2023), que no son más que este
archivo agrupado por coordenada con una media simple. Cubre 2019-02-08 a 2026-05.

Consecuencia práctica: **no hay dos linajes**, hay uno solo. Y el test de estacionalidad de
§7.2, que se daba por imposible, sí se puede correr.

## 3. La geometría NO permite descartar el glint en Colombia

Sentinel-5P cruza el ecuador a las ~13:30 hora solar local. Ángulo cenital solar al paso
del satélite, calculado como `cos(SZA) = sin(φ)sin(δ) + cos(φ)cos(δ)cos(h)` con ángulo
horario `h = 22.5°`:

| latitud | Ene | Mar | Jun | Sep | Dic |
|---|---|---|---|---|---|
| La Mojana 9.0°N | 37.5° | 25.3° | 25.8° | 23.4° | 39.1° |
| Bogotá 4.0°N | 33.5° | 23.5° | 29.1° | 22.5° | 35.0° |
| Amazonas 3.0°S | 28.5° | 22.5° | 34.2° | 23.1° | 29.8° |
| Guajira 12.0°N | 39.9° | 26.8° | 24.2° | 24.3° | 41.6° |

TROPOMI barre *across-track* de 0° a ~60°. Como el SZA (22–39°) **cae dentro** de ese
rango, siempre existe una posición del swath donde VZA = SZA y el ángulo de glint llega a
0°. Para SZA = 39°, la zona de glint (Θg < 20°, umbral típico) cubre VZA de 20° a 50°.

> **No se puede escribir que "el glint no aplica en latitudes tropicales".** Es al revés:
> el trópico es donde TROPOMI más observa en glint. Un revisor que conozca S5P lo sabrá.

Fórmula del ángulo de glint usada (reflexión especular conserva el cenital e invierte el
azimut): `cos(Θg) = cos(VZA)cos(SZA) − sin(VZA)sin(SZA)cos(Δφ)`.

## 4. Evidencia empírica: la firma del glint no está

El glint produce una **predicción falsable**: la contaminación debe crecer monótonamente
con el área de superficie especular del píxel. Se probó como dosis-respuesta.

### 4.1 Dentro de La Mojana (bbox 8.0–9.4°N, 75.2–74.3°W)

Los píxeles vecinos comparten geometría de observación, así que el contraste local
controla por el glint. Composición del área: 19.5 % agua abierta (sobre todo
`5.1.2 Lagunas, lagos y ciénagas naturales`) y 15.9 % humedal (`4.1.1 Zonas pantanosas`).

| fracción de **agua abierta** | n | Δ CH₄ vs seco |
|---|---|---|
| 0 | 7,692 | +0.00 |
| 0–15 % | 1,263 | +2.7 |
| 15–50 % | 1,549 | +3.4 |
| 50–75 % | 730 | +1.0 |
| **> 75 %** | 1,217 | **−1.8** |

**No es monótona y se invierte donde más superficie especular hay.** Lo contrario de lo
que exige la hipótesis de glint.

| fracción de **humedal** | Δ CH₄ vs seco |
|---|---|
| 0–5 % | +4.4 |
| 50–75 % | +5.1 |
| > 75 % | +5.8 |

El humedal —vegetación emergente, incapaz de reflexión especular— sí es monótono.

### 4.2 Contraintuitivo: el mar es lo más plano

A escala nacional, separando las clases de nivel 3:

| clase | Δ CH₄ en la cola alta (> 75 %) | forma |
|---|---|---|
| agua **marina** 5.2.x | +4.3 ppb | **plana**, sin dosis-respuesta |
| agua **continental** 5.1.x | +19.9 ppb | dosis-respuesta fuerte |
| humedal 4.x | +20.4 ppb | dosis-respuesta fuerte |

Justo donde el glint domina la recuperación (océano) la señal es la más débil y la más
plana. Si el glint inflara el CH₄, el océano sería el peor caso, no el mejor.

> Se descartó una hipótesis intermedia: se supuso que el realce nacional del agua vendría
> del mar. Es falso, y queda registrado para no volver a plantearlo.

### 4.3 El efecto también aparece DENTRO del mismo píxel a lo largo del tiempo

Añadido el 2026-07-28, del análisis causal (§4 del notebook). Es una línea de evidencia
independiente de todo lo anterior, y la más difícil de atribuir a un artefacto óptico.

En el panel bienal, cuando la fracción de **humedal vegetado** de un píxel *aumenta* entre
dos periodos de cobertura, su XCH₄ *sube*: +1.03 ppb por cada +10 puntos porcentuales
(≈ +10 ppb si el píxel se convirtiera entero, coherente con los +13 ppb del contraste
crudo de §5).

Por qué importa para el glint: la geometría de observación de un píxel la fijan su latitud
y la órbita, y **no cambia** porque cambie la cobertura. Si el realce fuera glint, la señal
tendría que ser constante en el tiempo para un píxel dado. Que suba y baje siguiendo la
fracción de humedal —una superficie con vegetación emergente, incapaz de reflexión
especular— no es compatible con un artefacto de reflectancia.

> **Caveat de potencia, no adornar.** El error estándar es ~0.5 ppb sobre un efecto de
> ~1 ppb, y los tres pares de bienios concuerdan en signo (9 de 10 clases entre los dos
> pares con más datos) pero no en magnitud. Esto se reporta como **corroboración de signo**
> por un segundo método, no como una estimación puntual. El par 2018→2020 está degenerado
> y se excluye. Ver el encabezado de §4 en el notebook.

### 4.4 La escala espacial no coincide con la del artefacto

Los píxeles **secos** dentro de La Mojana están en 1943.7 ppb frente a 1912.8 ppb del
resto del país: **+31 ppb regionales**, con contrastes internos de apenas ±5 ppb.

Este es el argumento más fuerte. Un artefacto de reflectancia superficial es **local al
píxel** por construcción: vive donde está la superficie especular. Lo observado es un
realce **regional** de escala ~100 km no anclado a los píxeles de agua. Un XCH₄ integra la
columna sobre el fetch de la capa límite, así que una fuente distribuida extensa produce
exactamente esta firma: fondo regional elevado y estructura sub-100 km difuminada.

## 5. Decisión adoptada en el pipeline

La máscara de calidad excluye **solo agua abierta** (nivel 1 = `5. Superficies de agua`)
por encima de 0.10, y píxeles con menos de 0.90 de cobertura clasificada. **Los humedales
se conservan**, por dos razones:

- El glint no aplica a vegetación emergente. Excluirlos nunca fue una decisión de calidad,
  fue daño colateral de usar "agua + humedal" como proxy geométrico del glint.
- Son la mayor fuente natural de CH₄ y en estos datos concentran la señal: 1925.4 ppb
  frente a 1912.5 ppb del fondo seco (+13 ppb, n = 27,594).

Efecto: 487,335 coordenadas válidas de 521,211 (93.5 %), frente a 444,202 del criterio
anterior — **+43,133 recuperadas**, de las cuales ~19,700 son de humedal.

La máscara guarda las fracciones además de la bandera `es_valido`, de modo que
re-umbralizar no exige repetir el cruce espacial (~90 min):

```python
df_valido = aplicar_mascara(df_combined)
df_valido = aplicar_mascara(df_combined, umbral_agua=0.25)   # sensibilidad
```

## 6. Cómo redactar la defensa

Plantearlo como test falsable, no como descargo:

> La geometría de observación de S5P sobre Colombia (SZA 22–39°) permite glint en parte
> del swath, por lo que se evaluó explícitamente. La hipótesis de contaminación por glint
> predice que la anomalía de XCH₄ crezca monótonamente con la fracción de superficie
> especular del píxel. En La Mojana la relación no es monótona y se invierte por encima
> del 75 % de agua abierta (−1.8 ppb), mientras que la fracción de humedal vegetado
> —incapaz de reflexión especular— sí muestra respuesta monótona (+5.8 ppb). A escala
> nacional, los píxeles marinos, donde las recuperaciones en glint dominan, presentan la
> respuesta más plana (+4.3 ppb). El realce de La Mojana es regional (+31 ppb sobre el
> fondo nacional, con contrastes internos < 5 ppb), incompatible con un artefacto de
> reflectancia, que sería local al píxel.

Acompañarlo de una **tabla de sensibilidad** al umbral de agua (`umbral_agua` ∈ {0.0,
0.05, 0.10, 0.25, 1.0}). Es la respuesta estándar a "¿y si el filtro cambia el resultado?".

## 7. Lo que falta para cerrarlo

### 7.1 Variables ausentes en el extracto actual

Las columnas de `CH4_glintfiltered_colombia_2019-2026.csv` son `id, longitude, latitude,
time, CH4_..._bias_corrected, date`. **No hay `qa_value`, ni ángulos, ni albedo.** Al
re-extraer de L2 `S5P_L2__CH4___` hay que incluir:

| variable | para qué |
|---|---|
| `qa_value` | reportar el filtro (≥ 0.5 es el estándar); hereda el cribado validado de SRON/ESA |
| `solar_zenith_angle`, `viewing_zenith_angle`, `solar_azimuth_angle`, `viewing_azimuth_angle` | calcular el ángulo de glint por sondeo |
| `surface_albedo_SWIR` | el glint se manifiesta como albedo SWIR anómalamente alto |
| `surface_classification` | distinguir tierra / agua / glint según la clasificación operacional |

**Test definitivo**: regresar la anomalía de XCH₄ sobre el ángulo de glint, píxel a píxel,
dentro de La Mojana. Si no hay dependencia, el argumento queda cerrado. Hoy solo se
infiere indirectamente desde la fracción de cobertura.

### 7.2 El test de estacionalidad SÍ es posible

Es el discriminador más limpio: la inundación de La Mojana es estacional e interanual (La
Niña 2020–2022), mientras que la geometría de glint no lo es. Si el realce sigue la
inundación, es emisión.

> **Corrección (2026-07-28).** Aquí se decía que no se podía correr, porque el único
> archivo con fechas "tiene cero píxeles de agua o humedal". Eso venía del error de §2: sus
> columnas de cobertura están vacías, no filtradas. `CH4_glintfiltered_colombia_2019-2026.csv`
> **sí conserva** los píxeles de agua y humedal — lo que le falta es la cobertura, y esa se
> le añade cruzándolo contra la máscara o contra el panel de §1.2.

Lo que hace falta para correrlo: agregar la serie por sondeo a resolución mensual dentro
del bbox (o mejor, del polígono oficial) de La Mojana, cruzarla con la fracción de humedal
y de agua abierta del panel, y contrastar el ciclo estacional del XCH₄ contra el ciclo de
inundación. Queda como trabajo disponible, no como imposible.

**Cuidado con el muestreo al hacerlo.** El número de sondeos por mes lo decide la nubosidad,
no el diseño, y el desbalance es severo: en 2020 enero y febrero aportan ~400,000 sondeos y
mayo-junio ~6,000; en 2019 enero tiene cero. Peor aún, el píxel mediano se observa muy pocos
meses (1 en 2019, 3 en 2022–2023). Medido sobre el par de bienios 2022→2024:

| meses observados | n | sd(ΔCH₄) | media ΔCH₄ |
|---|---|---|---|
| 1 | 133,287 | 31.6 ppb | +1.1 |
| 2 | 135,761 | 24.5 ppb | −3.2 |
| 3–4 | 137,834 | 16.8 ppb | +1.7 |
| 5–7 | 58,664 | 10.8 ppb | +6.2 |
| 8–12 | 30,169 | 7.1 ppb | +7.2 |

Los píxeles mal muestreados no solo añaden ruido: **añaden sesgo**, porque un promedio de un
solo mes cae donde caiga en el ciclo estacional. Por eso el panel de §1.2 promedia con los
meses equiponderados (media por píxel-mes, luego media entre meses) y arrastra `n_meses`
para poder filtrar. Cualquier análisis estacional tiene que hacer lo mismo.

### 7.3 Punto abierto

El **+19.9 ppb del agua continental** (5.1.x) a escala nacional no queda explicado. Lo más
probable es que sea real —ríos, ciénagas y embalses tropicales son fuentes documentadas de
CH₄, y aplica el mismo argumento de mezcla regional— pero con los datos actuales no se
puede separar emisión de un posible sesgo de recuperación sobre agua oscura continental.
Lo resolvería el albedo SWIR. Mientras tanto, mantener el filtro de agua abierta es la
postura conservadora, y por eso conviene reportarlo como filtro principal con la
sensibilidad al lado.

---

## Reproducibilidad

Todas las cifras salen de `Datos_a_05-2026/colombia_corr_metano_2022_2023_cobertura_2022.csv`
(831,455 filas; 521,211 coordenadas únicas de 2022+2023, cobertura 2022) salvo los conteos
de §2 y §7.2, que barren las 12,011,475 filas de
`CH4_glintfiltered_colombia_2019-2026.csv`, y la tabla de muestreo de §7.2, que sale de
`ch4_bienal_2022.csv` y `ch4_bienal_2024.csv` (generados en §1.2 del notebook).

El bbox de La Mojana usado es una aproximación (8.0–9.4°N, 75.2–74.3°W, 11,510 coordenadas
únicas). **Para publicar conviene sustituirlo por el polígono oficial de la región**, no
por un rectángulo.
