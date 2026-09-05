#!/usr/bin/env python3
"""Malla de covariables y unión canónica con la rejilla harp de S5P.

La malla de 0.01° proviene de harpconvert ``bin_spatial(2001, 50.0, 0.01,
2001, -120.0, 0.01)`` (§4.3 del notebook): bordes en −120.0 + k·0.01 de
longitud y 50.0 − k·0.01 de latitud, con centros de píxel terminados en
``.xx5``. La malla de 0.06° comparte el origen, de modo que cada celda de
0.06° contiene exactamente 6 × 6 celdas de 0.01°.

Este módulo es la única vía de unión de covariables a un DataFrame del
análisis (plan maestro §4: «nunca un merge a mano dentro de un análisis»).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ORIGEN_LON = -120.0
ORIGEN_LAT = 50.0
PASO_0P01 = 0.01
PASO_0P06 = 0.06
DECIMALES_COORD = 5
FACTOR_CELDA_0P06 = 100_000

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[1]
RUTA_COVARIABLES = RAIZ_REPOSITORIO / "scripts_2026" / "Datos_a_05-2026" / "covariables"
ARCHIVO_ESTATICAS = "estaticas_0p01.parquet"
DIRECTORIO_MENSUALES = "mensuales"
SUFIJO_MENSUAL = "_mensual"

LOGGER = logging.getLogger("covariables")


def redondear_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia con longitude/latitude redondeadas a 5 decimales."""
    copia = df.copy()
    for columna in ("longitude", "latitude"):
        copia[columna] = copia[columna].astype("float64").round(DECIMALES_COORD)
    return copia


def indices_malla(lon, lat, paso: float) -> tuple[np.ndarray, np.ndarray]:
    """(fila, columna) de cada coordenada en la malla harp global de ``paso`` grados."""
    lon = np.asarray(lon, dtype="float64")
    lat = np.asarray(lat, dtype="float64")
    columnas = np.floor((lon - ORIGEN_LON) / paso).astype("int64")
    filas = np.floor((ORIGEN_LAT - lat) / paso).astype("int64")
    return filas, columnas


def celda_0p06_id(lon, lat) -> np.ndarray:
    """Identificador int64 (fila·100000 + columna) de la celda de 0.06° contenedora.

    Sirve para agrupar errores por la celda fuente de las covariables de
    huella ~7 km (plan 03).
    """
    filas, columnas = indices_malla(lon, lat, PASO_0P06)
    return filas * FACTOR_CELDA_0P06 + columnas


def unir_covariables(
    df: pd.DataFrame,
    nombres: Sequence[str] | str,
    ruta: Path | str = RUTA_COVARIABLES,
) -> pd.DataFrame:
    """Une covariables a ``df`` por píxel de la malla CH4 (y por mes si aplica).

    ``nombres`` mezcla columnas de ``estaticas_0p01.parquet`` con nombres
    ``<variable>_mensual``, que unen ``mensuales/<variable>_0p01.parquet``
    por (longitude, latitude, year, month).

    Lanza ``ValueError`` si alguna fila de ``df`` no tiene píxel en la tabla
    estática. Para las mensuales reporta la cobertura y solo falla si es cero
    (meses sin dato son esperables, p. ej. albedo bajo nube persistente).
    """
    if isinstance(nombres, str):
        nombres = [nombres]
    if not nombres:
        raise ValueError("nombres no puede estar vacío")
    faltan_llaves = [c for c in ("longitude", "latitude") if c not in df.columns]
    if faltan_llaves:
        raise ValueError(f"df no tiene columnas {faltan_llaves}")
    ruta = Path(ruta)
    estaticos = [n for n in nombres if not n.endswith(SUFIJO_MENSUAL)]
    mensuales = [n for n in nombres if n.endswith(SUFIJO_MENSUAL)]
    resultado = redondear_coords(df)

    if estaticos:
        archivo = ruta / ARCHIVO_ESTATICAS
        if not archivo.is_file():
            raise FileNotFoundError(
                f"no existe {archivo}; ejecútese data_collection/collect_covariates_gee.py"
            )
        esquema = set(pq.read_schema(archivo).names)
        desconocidos = sorted(set(estaticos) - esquema)
        if desconocidos:
            raise KeyError(
                f"columnas {desconocidos} no están en {archivo.name}; "
                f"disponibles: {sorted(esquema - {'longitude', 'latitude'})}"
            )
        tabla = redondear_coords(
            pd.read_parquet(archivo, columns=["longitude", "latitude", *estaticos])
        )
        resultado = resultado.merge(
            tabla, on=["longitude", "latitude"], how="left", indicator="_union_estaticas"
        )
        sin_par = resultado["_union_estaticas"].eq("left_only")
        if sin_par.any():
            ejemplos = resultado.loc[sin_par, ["longitude", "latitude"]].head(5)
            raise ValueError(
                f"{int(sin_par.sum())} filas de df sin píxel en {archivo.name}; "
                f"ejemplos:\n{ejemplos.to_string(index=False)}"
            )
        resultado = resultado.drop(columns="_union_estaticas")
        for columna in estaticos:
            nulos = int(resultado[columna].isna().sum())
            if nulos:
                LOGGER.warning("%s tiene %d valores nulos tras la unión", columna, nulos)

    for nombre in mensuales:
        variable = nombre[: -len(SUFIJO_MENSUAL)]
        archivo = ruta / DIRECTORIO_MENSUALES / f"{variable}_0p01.parquet"
        if not archivo.is_file():
            raise FileNotFoundError(
                f"no existe {archivo}; ejecútese data_collection/collect_covariates_gee.py"
            )
        faltan = [c for c in ("year", "month") if c not in resultado.columns]
        if faltan:
            raise ValueError(f"la unión mensual de {variable} requiere columnas {faltan} en df")
        tabla = redondear_coords(pd.read_parquet(archivo))
        llaves = ["longitude", "latitude", "year", "month"]
        for llave in ("year", "month"):
            tabla[llave] = tabla[llave].astype("int64")
            resultado[llave] = resultado[llave].astype("int64")
        resultado = resultado.merge(tabla, on=llaves, how="left", indicator="_union_mensual")
        cobertura = float(resultado["_union_mensual"].eq("both").mean())
        if cobertura == 0.0:
            raise ValueError(f"ninguna fila de df encontró (píxel, mes) en {archivo.name}")
        LOGGER.info("Unión mensual de %s: %.1f %% de filas con dato", variable, 100 * cobertura)
        resultado = resultado.drop(columns="_union_mensual")

    return resultado
