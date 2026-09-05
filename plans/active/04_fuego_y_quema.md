# Plan 04 — Fuego y quema de biomasa: ¿emisión estable o combustión transitoria?

**Estado:** ⬜ pendiente · **Depende de:** 03 · **Desbloquea:** 09 · **Esfuerzo:** 2–3 días

## 1. Objetivo

Determinar si el efecto de las transiciones bosque → pasto/agrícola estimado en §4 es una
emisión **persistente** del nuevo uso del suelo (ganadería, suelo alterado) o el **pulso**
de CH₄ de la quema con la que se hace la deforestación, y controlar por ello.

## 2. Justificación científica

En Colombia la conversión de bosque se hace mayoritariamente por tala y quema en la
temporada seca (diciembre–marzo en Amazonía y Orinoquía). La combustión de biomasa emite
CH₄ (factor de emisión ~5–7 g CH₄/kg de materia seca en bosque tropical), y un frente de
fuego produce realces de columna detectables por TROPOMI durante días o semanas. Dos
cosas se alinean en contra del análisis actual:

1. **El muestreo de TROPOMI favorece la temporada seca** (cielo despejado), que es la de
   fuego. La media bienal del píxel está cargada hacia los meses en que, si hubo
   deforestación, hubo humo.
2. El cambio de cobertura entre dos capas del IGAC y la quema ocurren en el **mismo
   píxel y el mismo bienio**, así que el efecto fijo de par no los separa, y el
   bloque×par tampoco si el fuego es local.

Por tanto, una parte desconocida del coeficiente bosque→pasto puede ser combustión y no
el uso posterior del suelo. Para el artículo es una distinción de fondo: una es una
emisión puntual ya contabilizada en inventarios de quema; la otra es una emisión
recurrente del cambio de uso.

## 3. Insumos

| Insumo | Fuente | Resolución | Uso |
|---|---|---|---|
| Área quemada mensual | `MODIS/061/MCD64A1`, banda `BurnDate` | 500 m, mensual, 2000– | Fracción quemada por celda y mes |
| Fuego activo | `FIRMS` (MODIS) y, opcionalmente, VIIRS 375 m | 1 km / 375 m, diario | Fecha exacta y conteo de detecciones |
| Sondeos con fecha | `CH4_glintfiltered_colombia_2019-2026.csv` | por sondeo | Emparejar sondeo con fuego en ±k días/meses |
| Panel bienal y especificación canónica | plan 03 | — | Modelo base |

## 4. Pasos

### Paso 1 — Capas de fuego (1 día)

1. `collect_covariates_gee.py --layer burned_area`: por mes de 2019-01 a 2025-12,
   fracción del área de cada celda de 0.01° y 0.06° con `BurnDate > 0`. Salida
   `covariables/mensuales/fraccion_quemada_0p01.parquet`.
2. `--layer fire_counts`: conteo mensual de detecciones FIRMS por celda (confianza ≥ 30 %)
   y `dias_desde_ultimo_fuego`. Salida `covariables/mensuales/fuego_activo_0p01.parquet`.
3. Derivados por píxel-bienio: `fraccion_quemada_bienio` (máximo mensual y suma),
   `meses_con_fuego`, y a nivel de sondeo `fuego_en_ventana` (hubo quema en la celda o en
   un radio de 10 km en los 30 días previos al sondeo).
4. Chequeo de sanidad: el mapa de área quemada 2020 vs 2024 debe reproducir los patrones
   conocidos (arco de deforestación Caquetá–Guaviare–Meta; sabanas de la Orinoquía).

### Paso 2 — Fuego y cambio de cobertura se solapan (medio día)

Antes de modelar, medir el solapamiento: entre los píxeles que pierden > 10 pp de bosque
denso en un par, ¿qué fracción tiene área quemada en ese bienio? Y al revés. Un
diagrama de dispersión Δbosque vs. fracción quemada por par. Si el solapamiento es bajo
(< 20 %), el riesgo es menor y el plan termina antes.

### Paso 3 — Tres estimaciones para separar los mecanismos (1 día)

Sobre el agrupado canónico de §4:

| Esp. | Qué hace | Qué responde |
|---|---|---|
| F0 | Canónica | referencia |
| F1 | + `fraccion_quemada_bienio` como covariable | ¿parte del efecto es fuego? |
| F2 | CH₄ bienal recalculado **excluyendo** los sondeos con `fuego_en_ventana` | efecto sin el pulso de combustión |
| F3 | CH₄ bienal **solo** con sondeos con fuego en ventana (n será pequeño) | magnitud del pulso |

Lectura: si el coeficiente bosque→pasto cae > 50 % de F0 a F2, el efecto era sobre todo
combustión. Si se mantiene, es emisión del uso posterior. Reportar las tres con IC.

### Paso 4 — Interacción con estación seca (medio día)

Dividir el CH₄ bienal en medias de temporada seca (dic–mar) y húmeda (abr–nov) por
píxel y reestimar. Si el efecto aparece solo en la seca, apoya combustión (o menor
dilución por capa límite más baja); si aparece en ambas, apoya emisión estable. Esta
división sirve también al plan 05 (humedales emiten más en la húmeda).

### Paso 5 — Documentar

Celda "4.4 Fuego y quema" en el notebook con la tabla F0–F3 y la conclusión. Ficha en
`knowledge/covariables.md`.

## 5. Criterio de cierre

- [ ] Capas mensuales de área quemada y fuego activo 2019–2025 en `covariables/mensuales/`.
- [ ] Solapamiento fuego × pérdida de bosque cuantificado por par.
- [ ] Tabla F0–F3 con IC para las clases interpretables, en `resultados/causal_*_p04.csv`.
- [ ] Respuesta explícita: *el efecto bosque→pasto es [combustión | emisión estable |
      mezcla, con % atribuible al pulso]*.
- [ ] Decisión: la especificación canónica pasa a **excluir** sondeos con fuego en ventana
      (si F2 es estable y no pierde > 20 % de n) o a **incluir** la fracción quemada como
      covariable. Escribirla en `ESPECIFICACION_CANONICA`.

## 6. Qué va al artículo

- Resultado: descomposición del efecto de deforestación en pulso de quema y emisión
  persistente. Es probablemente uno de los dos o tres hallazgos centrales.
- Figura: coeficiente bosque→pasto en F0/F1/F2/F3, y por estación.

## 7. Riesgos

- MCD64A1 subestima quemas pequeñas bajo dosel; FIRMS compensa en parte. Decirlo.
- Excluir sondeos con fuego reduce `n_meses` y puede hacer que píxeles caigan por debajo
  de `MESES_MINIMOS`: reportar el n antes y después.
- El humo también afecta al retrieval (AOD alto): con el plan 02 cerrado, F1 debe
  incluir AOD para no confundir los dos canales.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
