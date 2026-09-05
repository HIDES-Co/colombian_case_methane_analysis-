# Plan 03 — Escala y diseño estadístico: agregación a la huella, efectos fijos bloque×par, errores de Conley y reglas para covariables gruesas

**Estado:** ⬜ pendiente · **Depende de:** 01, 02 · **Desbloquea:** 04–09 · **Esfuerzo:** 4–5 días

## 1. Objetivo

Fijar **la especificación canónica** de §3 y §4 con la que se evaluarán todas las
covariables de los planes siguientes, y resolver de paso los dos pendientes que el propio
notebook deja abiertos: el tamaño del bloque espacial (§4.2) y la escala del píxel (§4.3).
Este plan es el que sí modifica `ajustar_transversal` y `ajustar_causal`.

Cubre cuatro de los cinco puntos de la sección "técnica estadística" del análisis de
2026-08-23: (1) efectos fijos bloque×par, (3) errores de Conley, (4) pseudo-replicación
de covariables gruesas y el marco para (2) y (5), que se ejecutan en los planes 09 y 10.

## 2. Justificación

Tres hechos que ya están documentados en el notebook y aún no se han aplicado:

- **La malla es 6× más fina que la medición** (§4.3). A 0.01° las celdas vecinas dentro
  de una huella de 7 km comparten el mismo sondeo; no hay más información independiente
  que sondeos L2. Agregar a 0.06° no es una decisión de modelado sino deshacer un
  refinamiento artificial.
- **El bloque de 0.5° se eligió a ojo** (§4.2). Sin el diagnóstico, los errores estándar
  pueden estar subestimados (falsos positivos) o el número de bloques ser demasiado bajo
  (el par 2018-2020 corre con 64).
- **Los confusores temporales de §4 son regionales.** ENSO, la tasa de crecimiento del
  CH₄, el transporte y los meses observados varían suavemente en el espacio. El control
  más barato y más fuerte no es un dato externo: es **comparar cada píxel que cambió con
  sus vecinos del mismo bloque que no cambiaron, en el mismo bienio** (efecto fijo
  bloque×par). Eso absorbe todo confusor que sea común al bloque en ese par, sin necesidad
  de nombrarlo.

Y uno que llega con los planes 01–02: las covariables externas tienen resoluciones nativas
distintas (30 m el DEM, 500 m MODIS, 11–28 km ERA5/SMAP). Una covariable de 11 km repetida
en 120 celdas de 0.01° no aporta 120 observaciones; hay que tratarla como lo que es.

## 3. Pasos

### Paso 1 — Agregación a 0.06° (1 día)

1. Función `agregar_malla(df, lado=0.06)` que promedia, por celda de 0.06° alineada con la
   malla S5P, las fracciones de cobertura (igual área → media simple), el CH₄ (ponderado
   por `n_sondeos`), y arrastra `n_meses` (máximo), `n_sondeos` (suma) y las covariables
   de los planes 01–02 (media; `elev_std` como raíz de la media de varianzas).
   Nota que se documenta: se promedia sobre las celdas *presentes*, no sobre las 36
   teóricas; es la composición de la porción observada.
2. Correr §3 y §4 a 0.01°, 0.02°, 0.06° y 0.10°. **Mirar los coeficientes, no el R²**
   (§4.3): si solo se promedia ruido, los coeficientes no cambian; si hay desajuste de
   soporte, crecen en magnitud y se estabilizan. Tabla de coeficientes por escala para las
   clases interpretables.
3. Recontar las clases interpretables a 0.06° (el `p99` de las clases raras baja al
   mezclar). Decidir la lista definitiva y dejarla escrita.
4. **Decisión:** escala canónica. Se espera 0.06°; si los coeficientes siguen creciendo
   hasta 0.10°, elegir 0.06° igualmente y documentar la tendencia (más allá de 0.06° se
   pierde la variación de composición que identifica el efecto y aparece el problema de la
   unidad areal modificable).

### Paso 2 — Diagnóstico del bloque espacial, §4.2 (1 día)

Ejecutar el bloque ya escrito (celda [35]) sobre los residuos a la escala canónica, con
las covariables de 01–02 en el modelo, por las dos vías:

1. Vía 2 (directa): reajustar una vez y recalcular la covarianza agrupada con lados
   0.25°, 0.5°, 0.75°, 1.0°, 1.5°, 2.0°, más HC3 como "sin corrección". Curva de error
   estándar vs. lado para 4–5 coeficientes interpretables. El lado canónico es el
   **más pequeño donde la curva se aplana**.
2. Vía 1 (variogramas como cotas): correr los tres variogramas y reportar los rangos.
   Comprobar que el lado elegido en la vía 2 cae entre la cota inferior y la superior.
3. Vigilar `n_bloques`: si el lado elegido deja < 50 bloques en algún par, ese par se
   reporta con la advertencia y no entra en el agrupado principal (el 2018-2020 ya está
   excluido por degenerado).

### Paso 3 — Errores estándar de Conley (1 día)

Los bloques tienen un defecto estructural: dos píxeles a 1 km uno de otro, a lados de la
frontera de un bloque, se tratan como independientes. La alternativa estándar es el
estimador HAC espacial de Conley (1999): la covarianza de los scores se pondera con un
núcleo decreciente con la distancia hasta un ancho de banda `h`, sin fronteras.

1. Implementar `cov_conley(X, resid, lon, lat, h_km, kernel='bartlett')` en `common/`.
   Con n ~ 10–20 k a 0.06° la matriz de distancias cabe en memoria (n² · 8 bytes ≈ 3 GB
   para 20 k; usar `float32` o un árbol KD con `query_ball` para n mayores). Para n a
   0.01° (300 k) **no** se intenta: trabajar a la escala canónica.
2. Validar contra `statsmodels` en un caso trivial: con `h → 0` debe reproducir HC0; con
   un núcleo uniforme y `h` igual al lado del bloque, acercarse al agrupado.
3. Barrer `h` = 50, 100, 150, 200 km y reportar la curva de error estándar; elegir el `h`
   donde se aplana, contrastar con la horquilla física de 50–150 km (§4.2).
4. **Decisión:** la especificación canónica reporta errores de Conley; el agrupado por
   bloque queda como robustez en el suplemento. (Si la implementación resulta inestable,
   invertir: bloque canónico, Conley en robustez. Documentar.)

Nota práctica: si en el momento de ejecutar `pyfixest` ya ofrece errores de Conley en la
versión instalada, usarlo y validar la implementación propia contra él; en R existe
`fixest::vcov_conley` para contrastar.

### Paso 4 — Efectos fijos bloque×par en §4 (medio día)

1. En `ajustar_causal`, añadir `efectos_fijos_bloque_par=True`: indicadoras de
   (bloque de `LADO_EF` × par). `LADO_EF` debe ser **mayor que la huella atmosférica**
   (ver §4.2: 50–150 km) para que los vecinos no estén tratados por desbordamiento;
   empezar con 1.0° y probar 0.5° y 2.0°.
   Con cientos de indicadoras conviene absorberlas por demeaning dentro de grupo en lugar
   de `get_dummies` (`linearmodels.PanelOLS` con `other_effects`, o `pyfixest`).
2. Comparar el agrupado con (i) solo efecto fijo de par [actual], (ii) bloque×par a 1°,
   (iii) bloque×par a 0.5°. Si los coeficientes bajan al afinar el bloque, parte de lo que
   absorbía el bloque era el propio desbordamiento del tratamiento (atenuación por
   SUTVA): ese es el argumento para el núcleo del paso 5.
3. El R² "dentro" (within) es el que se reporta; el R² total con efectos fijos no
   significa nada aquí.

### Paso 5 — Núcleo suavizado de la exposición, §4.3 (1 día)

1. `suavizar_exposicion(df, h_km, kernel='gaussiano')`: convolución de las fracciones de
   cobertura con un núcleo isotrópico. Barrer `h` = 0 (sin suavizar), 10, 25, 50, 100 km.
2. Elegir `h` donde el ajuste deja de mejorar (criterio: log-verosimilitud o R² within con
   validación por bloques espaciales, **no** en muestra). El `h` elegido es una estimación
   de la huella atmosférica efectiva y se compara con la horquilla física.
3. El núcleo anisotrópico (a barlovento) queda para el plan 06, cuando haya viento.

### Paso 6 — Reglas para covariables gruesas (medio día)

Escribir en `knowledge/covariables.md` y aplicar en `unir_covariables`:

- Toda covariable con resolución nativa > escala canónica lleva su **identificador de
  celda fuente** (`<var>_celda`).
- Los errores estándar se agrupan, como mínimo, a la mayor de (bloque canónico, celda
  fuente de la covariable más gruesa del modelo). Con Conley, `h` ≥ tamaño de esa celda.
- Una covariable gruesa **no** entra interpolada bilinealmente por defecto (vecino más
  cercano), y nunca se describe con la resolución de la malla S5P.
- Para comprobar que no se inventa información: regresión auxiliar de la covariable
  sobre indicadoras de su celda fuente debe dar R² = 1.

### Paso 7 — Refactor y especificación canónica (medio día)

1. `ajustar_transversal(df, covariables=[...], cov='conley'|'cluster', ...)` y
   `ajustar_causal(df, covariables=[...], efectos_fijos='par'|'bloque_par', cov=..., ...)`.
2. Una celda de configuración en §3 con `ESPECIFICACION_CANONICA = dict(escala=0.06,
   lado_bloque=..., h_conley_km=..., lado_ef=..., h_exposicion_km=..., covariables=[...])`.
   Todos los planes posteriores la importan y **solo añaden covariables**.
3. Reejecutar §3 y §4 completos con la canónica y actualizar las celdas markdown de
   resultados ("Cómo leer estos resultados") con las cifras nuevas. Marcar §4.2 y §4.3
   como ✅ en la tabla de estado del notebook.

## 4. Criterio de cierre

- [ ] Tabla de coeficientes por escala (0.01/0.02/0.06/0.10) con la lectura de estabilización.
- [ ] Lado de bloque y `h` de Conley elegidos por la curva de error estándar, con la figura.
- [ ] Comparación par-FE vs. bloque×par-FE (1°, 0.5°) reportada.
- [ ] `h` de exposición elegido por validación espacial y comparado con 50–150 km.
- [ ] `ESPECIFICACION_CANONICA` escrita y §3/§4 reejecutados con ella.
- [ ] Reglas de covariables gruesas escritas en `knowledge/covariables.md`.
- [ ] Tabla de estado del notebook actualizada (§4.2, §4.3).

## 5. Qué va al artículo

- Métodos: subsección "Escala de análisis e inferencia espacial" (agregación a la huella,
  Conley, efectos fijos bloque×par, núcleo de exposición como estimación de la huella
  atmosférica efectiva).
- Suplemento: curvas de error estándar vs. lado/`h`; coeficientes vs. escala.

## 6. Riesgos

- El bloque×par puede absorber parte del tratamiento si el bloque es menor que la huella.
  Por eso `LADO_EF` ≥ 1° y el contraste con el núcleo.
- Conley con muestra irregular (malla dispersa) necesita un núcleo que no dé pesos
  negativos en la matriz (Bartlett es seguro).
- El refactor toca funciones que §4.1 (atribución nacional) consume: correr §4.1 después
  y comprobar que las cifras nacionales cambian solo por los coeficientes, no por un error
  de interfaz.

## 7. Registro de avance

- 2026-08-23 — Plan creado.
