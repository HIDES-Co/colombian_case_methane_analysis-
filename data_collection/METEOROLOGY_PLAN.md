# Plan de incorporacion de meteorologia

## Estado

Este documento define la segunda fase del recolector. La implementacion actual
solo descarga metano Sentinel-5P. No se deben agregar variables meteorologicas
al flujo principal hasta medir y validar primero la descarga completa de CH4.

## Objetivo

Asociar a cada observacion L3 de CH4 las condiciones meteorologicas mas cercanas
en tiempo y espacio, conservando la resolucion y procedencia reales de cada
variable. El resultado no debe presentar ERA5 como si tuviera la resolucion de
1.1 km de la malla S5P.

## Fuentes propuestas

| Prioridad | Coleccion GEE | Resolucion | Uso |
|---|---|---:|---|
| 1 | `ECMWF/ERA5_LAND/HOURLY` | 11.1 km, horaria | Temperatura, humedad, viento, presion y precipitacion sobre tierra |
| 2 | `ECMWF/ERA5/HOURLY` | 27.8 km, horaria | Altura de capa limite, nubosidad y variables atmosfericas no presentes en ERA5-Land |
| Alternativa | `MODIS/061/MOD11A1` | 1 km, diaria | Temperatura radiometrica de superficie, no temperatura meteorologica del aire |

MODIS LST no debe sustituir `temperature_2m`: mide la temperatura de la
superficie, tiene una hora de paso distinta y solo se recupera en condiciones
despejadas.

## Variables iniciales

Perfil `era5-land`:

| Banda | Unidad original | Salida derivada opcional |
|---|---:|---|
| `temperature_2m` | K | `temperature_2m_c` |
| `dewpoint_temperature_2m` | K | `relative_humidity_2m` |
| `u_component_of_wind_10m` | m/s | `wind_speed_10m` y direccion |
| `v_component_of_wind_10m` | m/s | `wind_speed_10m` y direccion |
| `surface_pressure` | Pa | `surface_pressure_hpa` |
| `total_precipitation_hourly` | m | `precipitation_hourly_mm` |

Perfil atmosferico adicional:

| Banda | Coleccion | Justificacion |
|---|---|---|
| `boundary_layer_height` | ERA5 Hourly | Mezcla vertical y dispersion de emisiones |
| `total_cloud_cover` | ERA5 Hourly | Contexto de disponibilidad y sesgo de observacion |

Las bandas originales siempre se conservaran. Las conversiones se calcularan
localmente y se documentaran, sin sustituir los valores fuente.

## Union temporal

Cada imagen S5P tiene un `system:time_start`. Para ella se seleccionara la
imagen ERA5 horaria que minimice la diferencia absoluta de tiempo, con una
tolerancia maxima inicial de 90 minutos.

Cada fila enriquecida debera incluir:

- `meteorology_source`.
- `meteorology_time` en UTC.
- `meteorology_time_offset_minutes` con signo.
- Una bandera que indique si la tolerancia fue satisfecha.

No se usara la fecha local como clave de union. La comparacion se realizara con
instantes UTC.

## Union espacial

La primera implementacion usara vecino mas cercano en la proyeccion nativa de
ERA5. No se aplicara interpolacion bilineal por defecto y no se describiran los
valores resultantes como datos de 1.1 km.

Se agregaran identificadores de la celda fuente:

- `era5_grid_x`.
- `era5_grid_y`.
- `era5_source_longitude`.
- `era5_source_latitude`.
- `era5_native_scale_m`.

Esto permitira agrupar errores y modelos por celda meteorologica, evitando que
la repeticion del mismo valor en muchos pixeles S5P se interprete como
informacion meteorologica independiente.

## Arquitectura propuesta

1. Agregar `--meteorology none|era5-land|era5-combined`, con `none` como valor predeterminado.
2. Resolver la imagen meteorologica mas cercana dentro de cada trabajo por orbita S5P.
3. Anadir las bandas ERA5 y las coordenadas de su celda al `ee.Image` antes del unico `Image.sample()`.
4. Aplicar a toda la pila la mascara de la banda CH4 corregida para no descargar pixeles donde S5P no tiene observacion.
5. Mantener la misma paginacion, paralelismo, reintentos y escritura atomica del recolector de CH4.
6. Escribir la salida enriquecida en un directorio diferente, porque su esquema y configuracion son incompatibles con el dataset CH4 base.
7. Registrar en `_collection_config.json` la coleccion ERA5, bandas, regla temporal, tolerancia y metodo espacial.

No se descargaran las 24 horas diarias de ERA5 sobre toda Colombia. Solo se
consultara la hora necesaria para cada orbita S5P y se devolveran los pixeles
en los que existe CH4. Esto reduce solicitudes, filas y almacenamiento.

## Controles cientificos

- Comparar la hora ERA5 elegida con la hora de cada imagen S5P.
- Verificar conversion de Kelvin a Celsius con casos conocidos.
- Verificar velocidad del viento como `sqrt(u^2 + v^2)`.
- Validar humedad relativa contra una implementacion de referencia y limitar solamente el resultado derivado a 0-100 %.
- Usar `total_precipitation_hourly`, no la acumulacion reiniciada a medianoche.
- Comprobar que todos los pixeles con el mismo identificador ERA5 comparten los mismos valores fuente.
- Comparar puntos de ciudades y regiones de distinta elevacion en Colombia.
- Reportar por separado faltantes S5P y faltantes meteorologicos.
- Conservar unidades y metadatos de las colecciones fuente.

## Pruebas de rendimiento

Antes de habilitar el perfil por defecto se ejecutaran tres comparaciones sobre
un mismo mes:

| Corrida | Proposito |
|---|---|
| Solo CH4 | Linea base de tiempo, EECU y tamano |
| CH4 + ERA5-Land | Costo de las seis variables iniciales |
| CH4 + ERA5-Land + ERA5 atmosferico | Costo de capa limite y nubosidad |

Se registraran imagenes por minuto, filas por segundo, bytes Parquet por fila,
reintentos, fallos y tiempo EECU cuando este disponible en Cloud Monitoring.

## Criterios de aceptacion

- Cero cambios en filas, coordenadas y CH4 frente a una corrida base del mismo periodo.
- Diferencia temporal absoluta menor o igual a 90 minutos para todas las filas no nulas.
- Resolucion y celda ERA5 identificables en cada fila.
- Reanudacion sin duplicados despues de una interrupcion.
- Pruebas unitarias de conversion y seleccion temporal.
- Smoke test en vivo sobre una orbita y comparacion manual con el catalogo GEE.
- Documentacion de licencia y atribucion Copernicus C3S/ECMWF en productos derivados.

## Riesgos conocidos

- ERA5-Land representa una rejilla de modelo, no una estacion meteorologica.
- Viento y temperatura pueden perder variacion local en valles y montanas colombianas.
- La altura de capa limite de ERA5 tiene una resolucion aun mas gruesa.
- La interpolacion de valores gruesos a la malla S5P puede producir pseudorreplicacion si no se modela la celda fuente.
- ERA5-Land publica incidencias conocidas en algunas bandas de evaporacion; no forman parte del perfil inicial.
- La precipitacion agregada puede contener pequenos valores negativos por el empaquetado GRIB; se conservara el dato fuente y cualquier correccion sera explicita.

Referencias oficiales:

- [ERA5-Land Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY)
- [ERA5 Hourly](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_HOURLY)
- [ERA5-Land Daily Aggregated](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR)
- [MODIS MOD11A1](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A1)
