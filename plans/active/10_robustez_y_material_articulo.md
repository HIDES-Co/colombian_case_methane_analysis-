# Plan 10 — Robustez (double machine learning), tabla de sensibilidad y material del artículo

**Estado:** ⬜ pendiente · **Depende de:** 01–09 · **Desbloquea:** redacción del artículo · **Esfuerzo:** 4–5 días

## 1. Objetivo

Cerrar la investigación con tres entregables: (a) una estimación del efecto que no
dependa de la forma funcional lineal en las covariables —*double machine learning*—,
(b) una **tabla de sensibilidad única** que muestre cómo se mueve cada coeficiente a lo
largo de toda la secuencia de planes, y (c) las figuras, tablas y cifras que van al
artículo, generadas por código reproducible desde los resultados guardados. Es el punto
(5) de la sección de técnica estadística y el cierre de los otros cuatro.

## 2. Justificación

Después de los planes 01–09 el modelo tendrá del orden de 15–25 covariables, varias con
relación no lineal con XCH₄ (elevación, albedo, humedad del suelo) e interacciones. Dos
objeciones quedan abiertas:

1. *"Con tantas covariables y una señal de 1 ppb, el resultado es el que usted eligió."*
   La respuesta es la tabla de sensibilidad: todos los coeficientes, en todas las
   especificaciones, en un solo lugar, y una lectura honesta de cuáles son estables.
2. *"La linealidad en las covariables es un supuesto; si la relación con la altitud o el
   albedo es curva, el control es incompleto."* La respuesta es DML (Chernozhukov et al.
   2018): se estima `E[Y|Z]` y `E[X|Z]` con un método flexible (bosque aleatorio, gradient
   boosting) por validación cruzada, y se regresa residuo sobre residuo. Da inferencia
   válida (raíz-n) sin imponer forma funcional a los confusores, y como chequeo de
   heterogeneidad el bosque causal estima el efecto por subpoblación.

## 3. Pasos

### Paso 1 — DML sobre la especificación final (2 días)

1. Unidad: píxel-periodo a la escala canónica (n ~ 10–20 k por periodo; manejable) con
   la respuesta y covariables de la canónica final. Tratamiento: vector de fracciones de
   cobertura (multi-tratamiento lineal) o, más simple y más robusto, una transición a la
   vez (p. ej. Δbosque denso → pasto) con las demás fracciones como controles.
2. `econml` (`LinearDML`, `CausalForestDML`) o `doubleml`; añadir al grupo `analysis`.
   Modelos de primera etapa: gradient boosting con validación cruzada por **bloques
   espaciales** (no aleatoria: con datos espaciales la validación aleatoria filtra
   información entre pliegues).
3. Reportar el efecto DML con IC junto al OLS de la canónica. Concordancia = robustez a
   la forma funcional; discrepancia = hay no linealidad relevante, y se investiga cuál
   (dependencia parcial de la primera etapa).
4. Bosque causal: efecto de Δbosque→pasto por región, altitud y estado hídrico. Si la
   heterogeneidad coincide con la de los planes 05 y 08, se refuerzan mutuamente.

### Paso 2 — Tabla de sensibilidad única (1 día)

Un script (`scripts_2026/Scripts/tabla_sensibilidad.py` o celda final) que lee todos los
`resultados/*_pNN.csv` y construye, para las clases interpretables:

| clase | §3 orig | §3 +elev (01) | §3 +retrieval (02) | §4 orig | §4 canónica (03) | +fuego (04) | +hídrico (05) | +meteo (06) | realce CAMS (07) | +antrópico (08) | sondeo TWFE (09) | DML (10) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

con efecto por +10 pp e IC. Y un gráfico de "specification curve": cada coeficiente
ordenado por magnitud a lo largo de las especificaciones, con el signo marcado. Las clases
cuyo signo se mantiene en todas las columnas son las que el artículo afirma; las que
cambian, se reportan como no concluyentes. Esa frase es la conclusión metodológica.

### Paso 3 — Atribución nacional con la canónica final (medio día)

Reejecutar §4.1 con los coeficientes finales (TWFE o DML, el que se elija en 09/10) y
con propagación de incertidumbre (bootstrap por bloques sobre coeficientes × Δárea).
Cifra nacional en ppb de media nacional por transición, con IC.

### Paso 4 — Material del artículo (1.5 días)

Generado por código desde `resultados/`, con estilo uniforme (cargar `dataviz` antes de
graficar), en `scripts_2026/articulo/`:

| Ítem | Origen |
|---|---|
| Fig. 1 — mapa de XCH₄ medio y cobertura nivel 1 | §1, §2 |
| Fig. 2 — XCH₄ vs. elevación con curva teórica | plan 01 |
| Fig. 3 — coeficientes por clase: transversal vs. causal vs. TWFE (con IC) | 03, 09 |
| Fig. 4 — estudio de eventos de pérdida de bosque | 09 |
| Fig. 5 — descomposición del efecto de deforestación: pulso de quema vs. persistente | 04 |
| Fig. 6 — efecto de humedales por par con ONI | 05 |
| Fig. S1 — control positivo: perfiles radiales de fuentes puntuales | 08 |
| Fig. S2 — curvas de error estándar vs. bloque / Conley; coeficientes vs. escala | 03 |
| Fig. S3 — specification curve | 10 |
| Tabla 1 — especificación canónica y covariables (fuente, resolución, papel) | `knowledge/covariables.md` |
| Tabla 2 — efectos finales por clase e IC | 09/10 |
| Tabla S1 — sensibilidad completa | 10 |

### Paso 5 — Cierre documental (medio día)

1. `knowledge/covariables.md` completo; `knowledge/NN_notebook.md` actualizado con las
   secciones nuevas; tabla de estado del notebook al día.
2. Mover los planes cerrados a `plans/done/` con su sección "Cierre".
3. Redactar en `knowledge/` un resumen de 1–2 páginas "qué afirmamos y con qué evidencia",
   que es el esqueleto de resultados y discusión del artículo.

## 4. Criterio de cierre

- [ ] Efecto DML con IC para las transiciones principales, comparado con OLS canónico.
- [ ] Heterogeneidad por bosque causal reportada y contrastada con 05 y 08.
- [ ] Tabla de sensibilidad y specification curve generadas por código desde `resultados/`.
- [ ] Lista explícita de clases con signo estable en todas las especificaciones.
- [ ] Atribución nacional con IC por bootstrap de bloques.
- [ ] Todas las figuras y tablas del artículo generadas desde código en `scripts_2026/articulo/`.
- [ ] Documentación cerrada y planes movidos a `plans/done/`.

## 5. Riesgos

- DML con tratamiento compositional (54 fracciones que suman 1) es incómodo; por eso se
  recomienda una transición a la vez con el resto como control.
- Validación cruzada espacial mal hecha infla la confianza; usar los bloques canónicos
  como pliegues.
- La tabla de sensibilidad expone todo, incluidos los resultados incómodos. Es su
  propósito; no se filtran columnas.

## 6. Registro de avance

- 2026-08-23 — Plan creado.
