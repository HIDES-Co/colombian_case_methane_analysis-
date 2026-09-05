# Plan 09 — Modelo de dos vías a nivel de sondeo y estudio de eventos de deforestación

**Estado:** ⬜ pendiente · **Depende de:** 03 (obligatorio), 04, 06 (deseables), 01–02, 05, 07, 08 (covariables) · **Desbloquea:** 10 · **Esfuerzo:** 5–7 días

## 1. Objetivo

Reemplazar la media bienal como unidad de análisis por el **sondeo individual** y estimar
el efecto de la cobertura con un modelo de efectos fijos de dos vías:

```
XCH₄_{i,t} = α_i + γ_{r(i), m(t)} + β · cobertura_{i, p(t)} + θ · Z_{i,t} + ε_{i,t}
```

donde `i` es el píxel (a la escala canónica), `t` el sondeo con fecha, `α_i` el efecto
fijo de píxel, `γ_{r,m}` el efecto fijo de región × mes calendario (año-mes), `p(t)` el
periodo de cobertura vigente en `t`, y `Z_{i,t}` las covariables que varían en el tiempo
(fuego, humedad del suelo, viento, AOD, versión del producto...). Es el punto (2) de la
sección de técnica estadística del análisis de 2026-08-23.

## 2. Justificación

El diseño actual de §4 hace primero la media bienal y después diferencia. Eso pierde
información y obliga a parches: equiponderar meses a mano, exigir `MESES_MINIMOS`,
descartar el par 2018-2020 por ralo. El modelo a nivel de sondeo:

- **usa los 12 M de sondeos** y deja que la precisión de cada píxel la decida su número
  de observaciones, con errores correctos;
- absorbe en `γ_{r,m}` la tendencia global (~+8 ppb/año), el ciclo estacional, la ITCZ,
  ENSO y la versión del producto, **por región y mes**, sin nombrar ninguno; es el
  bloque×par del plan 03 llevado a resolución mensual;
- admite cada covariable **en su tiempo nativo**: el fuego del mes, la humedad del suelo
  del mes, el viento de la hora;
- contiene al Δ bienal como caso particular (dos periodos, sin covariables), así que la
  comparación entre los dos es una prueba de consistencia, no un cambio de resultado;
- permite un **estudio de eventos**: mirar la trayectoria de XCH₄ de un píxel mes a mes
  antes y después de que pierde bosque, que es la evidencia visual más convincente de
  causalidad y hoy no existe en el notebook.

Lo que necesita y la cobertura del IGAC no da: **la fecha del cambio**. Las capas son
bienales; no se sabe en qué mes un píxel pasó de bosque a pasto. Para las transiciones de
pérdida de bosque, el año lo da `UMD/hansen/global_forest_change_*` (`lossyear`, 30 m,
anual), y el mes lo acota el fuego del plan 04.

## 3. Insumos

| Insumo | Fuente |
|---|---|
| Sondeos con fecha y bandas auxiliares | `CH4_glintfiltered_colombia_2019-2026.csv` o los parquet del recolector |
| Composición por píxel y periodo | `panel_bienal_cobertura_multianual.csv` (4 periodos) |
| Covariables estáticas y mensuales | `covariables/` (planes 01–08) |
| Año de pérdida de bosque | `UMD/hansen/global_forest_change_2024_v1_12` (`lossyear`, `treecover2000`) → fracción de la celda perdida por año |
| Herramienta | `pyfixest` (`feols` con `fe`, proyecciones alternantes) o `linearmodels.PanelOLS`; añadir con `uv add --group analysis pyfixest` |

## 4. Pasos

### Paso 1 — Tabla larga de sondeos (1 día)

1. Construir `sondeos_canonico.parquet`: un registro por sondeo con `pixel_id` (celda a
   la escala canónica), `fecha`, `year`, `month`, `region` (bloque de `LADO_EF`), XCH₄
   (y realce CAMS si existe), bandas auxiliares, `periodo_cobertura` (regla de
   emparejamiento de §1.2: 2019→2018, 2020–21→2020, 2022–23→2022, 2024–25→2024) y las
   covariables mensuales unidas por (`pixel_id`, `year`, `month`).
2. Aplicar la máscara de calidad del panel y las exclusiones decididas en 02/04/08.
3. Memoria: 12 M filas × ~40 columnas en `float32` ≈ 2 GB; trabajar con `pyarrow` y
   columnas seleccionadas. Si hace falta, submuestrear por píxel para desarrollo y correr
   completo una sola vez.

### Paso 2 — Modelo base y consistencia con §4 (1 día)

1. `feols(XCH4 ~ cobertura_k... | pixel_id + region^year_month, vcov={'CRV1': 'bloque'})`
   con las mismas clases y referencia de la canónica.
2. Comparar β con el agrupado de §4: correlación y tabla. Se espera la misma ordenación y
   magnitudes similares o algo mayores (menos atenuación por ruido de medias ralas).
3. Variante con `γ` a nivel nacional (`year_month` solo) para ver cuánto aporta región×mes.

### Paso 3 — Covariables en su tiempo nativo (1 día)

Añadir `Z_{i,t}` por bloques: (a) retrieval (AOD, altura de aerosol, ángulos, versión);
(b) fuego en ventana; (c) humedad del suelo y lluvia del mes; (d) viento de la hora. Tabla
de trayectoria. Esta es la especificación **final** del artículo; las anteriores son su
construcción.

### Paso 4 — Errores estándar (medio día)

Con `pixel_id` como efecto fijo, la dependencia temporal dentro de píxel se absorbe en
parte; la espacial no. Agrupar por bloque canónico (plan 03) y, como robustez, doble
agrupamiento bloque + año-mes. Conley a nivel de sondeo es inviable por n; reportarlo y
remitir a la escala agregada.

### Paso 5 — Estudio de eventos de pérdida de bosque (1.5 días)

1. Fracción de la celda con `lossyear` = 2019 … 2024 (Hansen). Un píxel es "tratado en
   el año y" si pierde > 10 pp de cobertura arbórea ese año y < 2 pp en los demás.
   Controles: píxeles del mismo bloque sin pérdida en 2019–2024.
2. Modelo de estudio de eventos: indicadoras de tiempo relativo al evento (−24 … +36
   meses, en trimestres), con efectos fijos de píxel y región×mes. Con tratamiento
   escalonado, usar un estimador robusto a heterogeneidad (Callaway–Sant'Anna o
   Sun–Abraham; `pyfixest` implementa Sun–Abraham) y no el TWFE ingenuo.
3. Figura: trayectoria media de XCH₄ de los tratados respecto a controles, con IC, por
   trimestre relativo. Lo que se busca: **sin tendencia previa** (pre-trends ≈ 0), un
   pulso en el trimestre del evento (quema) y un nivel posterior distinto de 0 (o no:
   ambos son resultados). Es el cruce directo con el plan 04.
4. Heterogeneidad: por región (Amazonía vs. Orinoquía vs. Andes) y por cobertura de
   destino (pasto vs. cultivo, según la capa IGAC siguiente).

### Paso 6 — Documentar

Sección nueva "4.7 Modelo a nivel de sondeo y estudio de eventos" en el notebook (o un
notebook aparte `scripts_2026/Scripts/sondeos_twfe.ipynb` si la memoria lo exige, con
enlace desde la tabla de estado).

## 5. Criterio de cierre

- [ ] `sondeos_canonico.parquet` construido y documentado (columnas, máscara, n).
- [ ] β del modelo base comparado con §4 (tabla + r); consistencia explicada.
- [ ] Especificación final con `Z_{i,t}`, tabla de trayectoria, errores por bloque y doble
      agrupamiento, en `resultados/twfe_sondeos_p09.csv`.
- [ ] Figura de estudio de eventos con pre-trends reportados y estimador robusto a
      tratamiento escalonado.
- [ ] Decisión: el resultado principal del artículo es el modelo a nivel de sondeo; §3 y
      §4 pasan a ser construcción y robustez. (O lo contrario, si el modelo a nivel de
      sondeo no es estable; escribir por qué.)

## 6. Qué va al artículo

- Resultado principal: tabla de efectos por clase con la especificación final.
- Figura central: estudio de eventos de pérdida de bosque.
- Métodos: el modelo, los efectos fijos y por qué la unidad es el sondeo.

## 7. Riesgos

- 600 k efectos fijos de píxel + miles de región×mes: `pyfixest` lo maneja por
  proyecciones alternantes, pero el tiempo de ajuste puede ser de decenas de minutos por
  especificación. Planificar las corridas; no iterar a ciegas.
- Hansen detecta pérdida de dosel, no conversión; una tala selectiva o un incendio sin
  cambio de uso también cuenta. Cruzar con la capa IGAC siguiente para confirmar destino.
- TWFE con tratamiento escalonado y efectos heterogéneos está sesgado (literatura
  2020–2022): por eso el estimador robusto es obligatorio, no opcional.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
