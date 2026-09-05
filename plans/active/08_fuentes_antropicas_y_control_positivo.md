# Plan 08 — Fuentes antrópicas fijas y control positivo de sensibilidad

**Estado:** ⬜ pendiente · **Depende de:** 01 · **Desbloquea:** 09, 10 · **Esfuerzo:** 2–3 días

## 1. Objetivo

Dos cosas con los mismos datos:

1. **Controlar y delimitar** las fuentes antrópicas de CH₄ que no son cobertura de la
   tierra —petróleo y gas, minería de carbón, rellenos sanitarios, ciudades— que en §3
   son confusores espaciales y en §4 pueden contaminar un píxel si su actividad cambia.
2. **Demostrar que el dato ve lo que debería ver.** Si el método no detecta las fuentes
   puntuales conocidas y fuertes de Colombia, un efecto de cobertura de ~1 ppb no es
   creíble. Un control positivo es la respuesta más corta a la objeción "el ruido de
   TROPOMI es mayor que su señal".

## 2. Justificación científica

Colombia tiene fuentes antrópicas de CH₄ concentradas y bien localizadas: producción de
hidrocarburos en el Magdalena Medio (Barrancabermeja), Llanos (Casanare, Meta: Rubiales,
Cupiagua, Cusiana), Putumayo y Catatumbo; minería de carbón a cielo abierto en Cesar y La
Guajira (Cerrejón) y subterránea en Cundinamarca–Boyacá (Cucunubá, Lenguazaque, Samacá),
que es la que más CH₄ emite por tonelada; rellenos (Doña Juana en Bogotá) y las áreas
metropolitanas. La ganadería es la mayor fuente antrópica nacional, pero esa **sí** la
representa la cobertura (pastos).

En §3 estas fuentes están donde están ciertas coberturas (pastos y cultivos de la
Orinoquía y el valle del Magdalena cerca de los campos) y sesgan los coeficientes. En §4
se cancelan si su emisión es constante, pero no lo es: la producción de gas y carbón varió
entre 2019 y 2025. Hay que poder marcar los píxeles afectados.

## 3. Insumos

| Insumo | Fuente | Resolución | Uso |
|---|---|---|---|
| Emisiones gridded por sector | EDGAR (última versión disponible), CH₄ por sector (`ENE`, `PRO_OIL`, `PRO_GAS`, `PRO_COAL`, `SWD_LDF`, `ENF`, `AGS`...) | 0.1°, anual | Densidad de emisión por píxel y sector |
| Infraestructura O&G | Climate TRACE (activos), base de datos global de infraestructura O&G, y nacional: ANH (campos, pozos, `Mapa de Tierras`) | vectorial | Distancia a campo/pozo más cercano |
| Minas de carbón | Climate TRACE (minería de carbón), ANM (títulos mineros) | vectorial | Distancia y tipo (cielo abierto / subterránea) |
| Luces nocturnas | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` (`avg_rad`) | 500 m, mensual | Proxy de actividad urbana/industrial y de antorchas (flaring) |
| Superficie construida | `JRC/GHSL/P2023A/GHS_BUILT_S` | 100 m | Fracción urbana |
| Población | `WorldPop/GP/100m/pop` | 100 m | Densidad |

EDGAR y las bases vectoriales no están en GEE: descarga directa y procesamiento local
con `geopandas`. Son remote sensing solo en parte (luces nocturnas, GHSL); su valor aquí
es de **confusor y control positivo**, no de variable explicativa principal.

## 4. Pasos

### Paso 1 — Capas estáticas (1 día)

1. EDGAR: regrillar 0.1° → 0.01°/0.06° (vecino más cercano, conservando la celda fuente)
   por sector: `edgar_ch4_total`, `edgar_ch4_oil_gas`, `edgar_ch4_coal`, `edgar_ch4_waste`,
   `edgar_ch4_agri`. Año más reciente disponible y, si hay serie, el cambio 2019→último año.
2. Distancias: `dist_campo_oag_km`, `dist_mina_carbon_km` (con tipo), `dist_relleno_km`,
   `dist_ciudad_100k_km`.
3. `luces_nocturnas_media` por año (sirve de variable temporal barata: cambia con la actividad).
4. `fraccion_construida`, `densidad_pob`.
5. Añadir a `covariables/estaticas_0p01.parquet` y documentar.

### Paso 2 — Control positivo (1 día)

1. Definir 6–10 fuentes puntuales conocidas (Cerrejón, Barrancabermeja, Cupiagua/Cusiana,
   Rubiales, cuenca carbonífera Cundinamarca–Boyacá, Doña Juana, Bogotá, Medellín) con
   coordenadas y emisión estimada (Climate TRACE / EDGAR).
2. Para cada una: realce medio de XCH₄ (o del realce CAMS si el plan 07 está cerrado) en
   anillos de 0–10, 10–25, 25–50, 50–100 km, por año, con IC por bloque. Una figura con
   los perfiles radiales.
3. Regresión simple realce ~ log(emisión) sobre las fuentes: pendiente positiva y
   significativa = el dato es sensible a fuentes de ese orden. Si la pendiente es nula,
   el artículo debe decir explícitamente que el método no resuelve fuentes puntuales y
   por qué sí resuelve coberturas extensas (área grande × emisión difusa).
4. Extensión opcional: orientar los anillos a barlovento con el viento del plan 06.

### Paso 3 — Control y exclusión en §3/§4 (medio día)

| Esp. | Qué hace |
|---|---|
| A1 | canónica + `edgar_ch4_oil_gas`, `edgar_ch4_coal`, `edgar_ch4_waste`, `fraccion_construida` |
| A2 | canónica excluyendo píxeles a < 25 km de una fuente puntual mayor |
| A3 | canónica + Δ`luces_nocturnas` (proxy del cambio de actividad, para §4) |

Tabla de trayectoria para las clases interpretables. Si A2 cambia poco los coeficientes,
la cobertura no está confundida con fuentes puntuales y se dice; si los cambia, A2 pasa a
ser parte de la canónica (o la máscara de calidad incorpora la exclusión).

### Paso 4 — Heterogeneidad (medio día)

Efecto de pastos y cultivos en píxeles con y sin O&G cerca: si el coeficiente de pasto es
mayor cerca de O&G, el "pasto" estaba recogiendo infraestructura. Dos líneas en la tabla.

## 5. Criterio de cierre

- [ ] Capas EDGAR, distancias, luces, construido y población en `estaticas_0p01.parquet`.
- [ ] Figura de perfiles radiales y pendiente realce ~ log(emisión) con IC.
- [ ] Respuesta explícita: *el dato [sí | no] resuelve fuentes puntuales de X t/año; la
      sensibilidad a coberturas extensas se justifica por ...*
- [ ] Tabla A1–A3 en `resultados/*_p08.csv` y decisión sobre exclusión en la canónica.

## 6. Qué va al artículo

- Suplemento (o resultados): control positivo — es el argumento de credibilidad del dato.
- Métodos: cómo se trató la confusión con fuentes antrópicas.

## 7. Riesgos

- EDGAR asigna emisiones con proxies espaciales gruesos; la distancia a activos reales es
  mejor para fuentes puntuales.
- Las bases nacionales (ANH, ANM) cambian de formato; guardar la versión usada.
- Las antorchas de gas emiten CH₄ incompletamente quemado; las luces nocturnas las ven y
  pueden servir de proxy de flaring donde no haya inventario.

## 8. Registro de avance

- 2026-08-23 — Plan creado.
