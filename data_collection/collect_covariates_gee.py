#!/usr/bin/env python3
"""Descarga covariables (DEM GLO30, albedo SWIR MCD43A3) de Earth Engine.

Estrategia (plan maestro §4/§6): exportar rásteres reducidos a la malla harp
de 0.01° y 0.06° (origen −120.0 / 50.0, la misma del producto S5P L3 de CH4),
recortados a Colombia, y muestrearlos localmente en los centros de píxel de la
malla CH4 — nunca enviar ~700 k puntos a Earth Engine.

Capas disponibles:

- ``--layer dem``: COPERNICUS/DEM/GLO30 (30 m). GeoTIFFs mean/stdDev a 0.01° y
  mean/stdDev/min/max a 0.06°; columnas ``elev_m``, ``elev_std_1km``,
  ``elev_std_7km``, ``elev_min_7km``, ``elev_max_7km`` en
  ``covariables/estaticas_0p01.parquet`` (plan 01, paso 1).
- ``--layer albedo_swir``: MODIS/061/MCD43A3 bandas 7 BSA/WSA (500 m, 2.1 µm)
  con máscara de calidad. Medias mensuales y anuales a 0.01° y 0.06°;
  ``covariables/mensuales/albedo_swir_0p01.parquet`` y columnas
  ``albedo_swir_<año>`` en las estáticas (plan 02, paso 2).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import re
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any, Callable, Sequence

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import ee  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import rasterio  # noqa: E402
from rasterio.errors import RasterioIOError  # noqa: E402
from rasterio.transform import Affine  # noqa: E402

from common.covariables import (  # noqa: E402
    ARCHIVO_ESTATICAS,
    DIRECTORIO_MENSUALES,
    ORIGEN_LAT,
    ORIGEN_LON,
    PASO_0P01,
    PASO_0P06,
    RUTA_COVARIABLES,
    celda_0p06_id,
    redondear_coords,
)
from data_collection.collect_gee_colombia import (  # noqa: E402
    COUNTRY_ASSET,
    COUNTRY_NAME,
    COUNTRY_PROPERTY,
    LAST_RUN_FILENAME,
    MANIFEST_FILENAME,
    CollectionError,
    append_manifest,
    colombia_geometry,
    initialize_earth_engine,
    is_retryable_error,
    lock_output_directory,
    positive_int,
    prepare_output_directory,
    worker_count,
    write_json_atomic,
    write_parquet_atomic,
)

COVARIATES_VERSION = 1
WORKLOAD_TAG = "covariables-colombia"

# Valor centinela con el que se rellenan los píxeles enmascarados antes de
# exportar; cualquier muestra por debajo de UMBRAL_NODATA se convierte en NaN.
NODATA_SENTINEL = -1_000_000.0
UMBRAL_NODATA = -100_000.0

DEM_DATASET = "COPERNICUS/DEM/GLO30"
DEM_BAND = "DEM"
DEM_RES_NATIVA_M = 30
REDUCTORES_DEM_0P01 = ("mean", "stdDev")
REDUCTORES_DEM_0P06 = ("mean", "stdDev", "min", "max")

MODIS_DATASET = "MODIS/061/MCD43A3"
MODIS_QA_BAND = "BRDF_Albedo_Band_Mandatory_Quality_Band7"
MODIS_BANDAS = {"bsa": "Albedo_BSA_Band7", "wsa": "Albedo_WSA_Band7"}
MODIS_ESCALA = 0.001
MODIS_RES_NATIVA_M = 500
TIPOS_ALBEDO = ("bsa", "wsa", "nobs")

# reduceResolution admite hasta 65536 píxeles de entrada por píxel de salida;
# el peor caso aquí es GLO30 (30 m) → 0.06° ≈ 222² ≈ 49 k.
MAX_PIXELS_REDUCCION = 65_535

ETIQUETAS_MALLA = {"0p01": PASO_0P01, "0p06": PASO_0P06}
CH4_CSV = RAIZ / "scripts_2026" / "Datos_a_05-2026" / "CH4_glintfiltered_colombia_2019-2026.csv"
ARCHIVO_MALLA_CH4 = "malla_ch4_0p01.parquet"

COLUMNAS_DEM = {
    "elev_m": "glo30_mean_0p01.tif",
    "elev_std_1km": "glo30_stdDev_0p01.tif",
    "elev_std_7km": "glo30_stdDev_0p06.tif",
    "elev_min_7km": "glo30_min_0p06.tif",
    "elev_max_7km": "glo30_max_0p06.tif",
}
UMBRAL_FRACCION_SIN_DEM = 0.25

LOGGER = logging.getLogger("collect_covariates_gee")


class RasterInvalidoError(CollectionError):
    """El GeoTIFF descargado no valida; se considera transitorio y se reintenta."""


class ErrorDescargaRaster(CollectionError):
    """Error definitivo al descargar un ráster."""

    def __init__(self, job: RasterJob, attempts: int, cause: Exception) -> None:
        super().__init__(f"{job.stem}: {cause}")
        self.job = job
        self.attempts = attempts
        self.cause = cause


@dataclass(frozen=True)
class MallaRaster:
    """Rejilla de exportación alineada con la malla harp global."""

    etiqueta: str
    paso: float
    lon_oeste: float
    lat_norte: float
    ancho: int
    alto: int

    @property
    def affine(self) -> Affine:
        return Affine(self.paso, 0.0, self.lon_oeste, 0.0, -self.paso, self.lat_norte)

    def grid_request(self) -> dict[str, Any]:
        return {
            "dimensions": {"width": self.ancho, "height": self.alto},
            "affineTransform": {
                "scaleX": self.paso,
                "shearX": 0.0,
                "translateX": self.lon_oeste,
                "shearY": 0.0,
                "scaleY": -self.paso,
                "translateY": self.lat_norte,
            },
            "crsCode": "EPSG:4326",
        }


@dataclass(frozen=True)
class RasterJob:
    """Un GeoTIFF por (capa, estadística/banda, resolución, periodo)."""

    layer: str
    stem: str
    subdir: str
    malla: MallaRaster
    builder: str
    params: tuple[Any, ...]

    def ruta(self, rasters_capa: Path) -> Path:
        base = rasters_capa / self.subdir if self.subdir else rasters_capa
        return base / f"{self.stem}.tif"


@dataclass(frozen=True)
class ResultadoRaster:
    job: RasterJob
    path: Path
    attempts: int
    duration_seconds: float
    bytes_escritos: int


@dataclass
class ResumenRasters:
    total: int = 0
    completados: int = 0
    omitidos: int = 0
    fallidos: int = 0


def malla_para_bbox(
    bbox: tuple[float, float, float, float], paso: float, etiqueta: str
) -> MallaRaster:
    """Ajusta el bbox hacia afuera a líneas de la malla harp de ``paso`` grados."""
    minx, miny, maxx, maxy = bbox
    lon_oeste = ORIGEN_LON + math.floor((minx - ORIGEN_LON) / paso) * paso
    lat_norte = ORIGEN_LAT - math.floor((ORIGEN_LAT - maxy) / paso) * paso
    ancho = math.ceil((maxx - lon_oeste) / paso - 1e-9)
    alto = math.ceil((lat_norte - miny) / paso - 1e-9)
    if ancho <= 0 or alto <= 0:
        raise CollectionError(f"bbox inválido para la malla {etiqueta}: {bbox}")
    return MallaRaster(
        etiqueta=etiqueta,
        paso=paso,
        lon_oeste=round(lon_oeste, 6),
        lat_norte=round(lat_norte, 6),
        ancho=ancho,
        alto=alto,
    )


def bbox_region(region: ee.Geometry) -> tuple[float, float, float, float]:
    """Bbox lon/lat de la región con una sola llamada getInfo compacta."""
    anillo = region.bounds(1).getInfo()["coordinates"][0]
    lons = [punto[0] for punto in anillo]
    lats = [punto[1] for punto in anillo]
    return min(lons), min(lats), max(lons), max(lats)


def mallas_colombia(region: ee.Geometry) -> dict[str, MallaRaster]:
    bbox = bbox_region(region)
    return {
        etiqueta: malla_para_bbox(bbox, paso, etiqueta)
        for etiqueta, paso in ETIQUETAS_MALLA.items()
    }


def rango_meses(inicio: str, fin: str) -> list[tuple[int, int]]:
    """Meses [inicio, fin) en formato YYYY-MM, fin exclusivo."""
    for valor in (inicio, fin):
        if not re.fullmatch(r"\d{4}-\d{2}", valor):
            raise CollectionError(f"los meses usan YYYY-MM: {valor!r}")
    anio_ini, mes_ini = int(inicio[:4]), int(inicio[5:7])
    anio_fin, mes_fin = int(fin[:4]), int(fin[5:7])
    if not 1 <= mes_ini <= 12 or not 1 <= mes_fin <= 12:
        raise CollectionError("mes fuera de rango en --start/--end")
    if (anio_ini, mes_ini) >= (anio_fin, mes_fin):
        raise CollectionError("--end debe ser posterior a --start (fin exclusivo)")
    meses: list[tuple[int, int]] = []
    anio, mes = anio_ini, mes_ini
    while (anio, mes) < (anio_fin, mes_fin):
        meses.append((anio, mes))
        anio, mes = _mes_siguiente(anio, mes)
    return meses


def _mes_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def jobs_dem(mallas: dict[str, MallaRaster]) -> list[RasterJob]:
    jobs = []
    for reductor in REDUCTORES_DEM_0P01:
        jobs.append(
            RasterJob("dem", f"glo30_{reductor}_0p01", "", mallas["0p01"], "dem", (reductor,))
        )
    for reductor in REDUCTORES_DEM_0P06:
        jobs.append(
            RasterJob("dem", f"glo30_{reductor}_0p06", "", mallas["0p06"], "dem", (reductor,))
        )
    return jobs


def jobs_albedo(
    mallas: dict[str, MallaRaster],
    meses: Sequence[tuple[int, int]],
    anios: Sequence[int],
    qa_max: int,
) -> list[RasterJob]:
    jobs = []
    for anio, mes in meses:
        inicio = f"{anio:04d}-{mes:02d}-01"
        anio2, mes2 = _mes_siguiente(anio, mes)
        fin = f"{anio2:04d}-{mes2:02d}-01"
        for tipo in TIPOS_ALBEDO:
            for etiqueta, malla in mallas.items():
                jobs.append(
                    RasterJob(
                        "albedo_swir",
                        f"albedo_{tipo}_{etiqueta}_{anio:04d}-{mes:02d}",
                        "mensual",
                        malla,
                        "albedo",
                        (tipo, inicio, fin, qa_max),
                    )
                )
    for anio in anios:
        for tipo in TIPOS_ALBEDO:
            for etiqueta, malla in mallas.items():
                jobs.append(
                    RasterJob(
                        "albedo_swir",
                        f"albedo_{tipo}_{etiqueta}_{anio:04d}",
                        "anual",
                        malla,
                        "albedo",
                        (tipo, f"{anio:04d}-01-01", f"{anio + 1:04d}-01-01", qa_max),
                    )
                )
    return jobs


def _imagen_dem(reductor: str) -> ee.Image:
    coleccion = ee.ImageCollection(DEM_DATASET).select(DEM_BAND)
    proyeccion = coleccion.first().projection()
    reductores = {
        "mean": ee.Reducer.mean(),
        "stdDev": ee.Reducer.stdDev(),
        "min": ee.Reducer.min(),
        "max": ee.Reducer.max(),
    }
    return (
        coleccion.mosaic()
        .setDefaultProjection(proyeccion)
        .reduceResolution(reductores[reductor], maxPixels=MAX_PIXELS_REDUCCION)
    )


def _imagen_albedo(tipo: str, inicio: str, fin: str, qa_max: int) -> ee.Image:
    coleccion = ee.ImageCollection(MODIS_DATASET).filterDate(inicio, fin)
    proyeccion = coleccion.first().select(0).projection()
    banda = MODIS_BANDAS["bsa" if tipo == "nobs" else tipo]

    def preparar(imagen: ee.Image) -> ee.Image:
        qa_ok = imagen.select(MODIS_QA_BAND).lte(qa_max)
        valida = imagen.select(banda).updateMask(qa_ok)
        if tipo == "nobs":
            return valida
        return valida.multiply(MODIS_ESCALA)

    preparada = coleccion.map(preparar)
    imagen = preparada.count() if tipo == "nobs" else preparada.mean()
    return (
        imagen.toFloat()
        .setDefaultProjection(proyeccion)
        .reduceResolution(ee.Reducer.mean(), maxPixels=MAX_PIXELS_REDUCCION)
    )


def expresion_para(job: RasterJob, region: ee.Geometry) -> ee.Image:
    if job.builder == "dem":
        imagen = _imagen_dem(*job.params)
    elif job.builder == "albedo":
        imagen = _imagen_albedo(*job.params)
    else:
        raise CollectionError(f"builder desconocido: {job.builder}")
    return imagen.clip(region).toFloat().unmask(NODATA_SENTINEL)


def escribir_bytes_atomico(datos: bytes, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")
    try:
        temporal.write_bytes(datos)
        os.replace(temporal, destino)
    finally:
        temporal.unlink(missing_ok=True)


def raster_valido(path: Path, malla: MallaRaster) -> bool:
    """Un GeoTIFF existente vale si su rejilla coincide exactamente con la esperada."""
    if not path.is_file():
        return False
    try:
        with rasterio.open(path) as src:
            if src.count != 1 or src.width != malla.ancho or src.height != malla.alto:
                return False
            esperado = malla.affine
            actual = src.transform
            return all(
                abs(a - b) <= 1e-9
                for a, b in zip(
                    (actual.a, actual.b, actual.c, actual.d, actual.e, actual.f),
                    (esperado.a, esperado.b, esperado.c, esperado.d, esperado.e, esperado.f),
                )
            )
    except (RasterioIOError, ValueError):
        return False


def descargar_raster(
    job: RasterJob,
    region: ee.Geometry,
    rasters_capa: Path,
    max_attempts: int,
    sleep: Callable[[float], None] = time.sleep,
    stop_event: Event | None = None,
) -> ResultadoRaster:
    """Descarga, valida y persiste atómicamente un GeoTIFF con reintentos acotados."""
    inicio = time.perf_counter()
    destino = job.ruta(rasters_capa)
    for intento in range(1, max_attempts + 1):
        if stop_event is not None and stop_event.is_set():
            raise CollectionError(f"descarga interrumpida antes de {job.stem}")
        try:
            payload = ee.data.computePixels(
                {
                    "expression": expresion_para(job, region),
                    "fileFormat": "GEO_TIFF",
                    "grid": job.malla.grid_request(),
                    "workloadTag": WORKLOAD_TAG,
                }
            )
            if not isinstance(payload, (bytes, bytearray)):
                raise CollectionError(f"respuesta inesperada de computePixels para {job.stem}")
            escribir_bytes_atomico(bytes(payload), destino)
            if not raster_valido(destino, job.malla):
                destino.unlink(missing_ok=True)
                raise RasterInvalidoError(f"GeoTIFF descargado inválido para {job.stem}")
            return ResultadoRaster(
                job=job,
                path=destino,
                attempts=intento,
                duration_seconds=time.perf_counter() - inicio,
                bytes_escritos=len(payload),
            )
        except Exception as exc:
            reintentable = isinstance(exc, RasterInvalidoError) or is_retryable_error(exc)
            if intento >= max_attempts or not reintentable:
                raise ErrorDescargaRaster(job, intento, exc) from exc
            espera = min(60.0, 2.0 ** (intento - 1)) + random.uniform(0.0, 0.5)
            LOGGER.warning(
                "%s falló en el intento %d/%d; reintento en %.1fs: %s",
                job.stem,
                intento,
                max_attempts,
                espera,
                exc,
            )
            if stop_event is None:
                sleep(espera)
            elif stop_event.wait(espera):
                raise CollectionError(f"descarga interrumpida mientras reintentaba {job.stem}")
    raise AssertionError("unreachable")


def _registro_raster(job: RasterJob, rasters_capa: Path) -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "raster": job.stem,
        "path": str(job.ruta(rasters_capa).relative_to(rasters_capa)),
    }


def ejecutar_descargas(
    jobs: Sequence[RasterJob],
    region: ee.Geometry,
    rasters_capa: Path,
    workers: int,
    max_attempts: int,
    overwrite: bool,
) -> ResumenRasters:
    """Descarga todos los rásteres serializando el registro de avance en el hilo principal."""
    resumen = ResumenRasters(total=len(jobs))
    manifest_path = rasters_capa / MANIFEST_FILENAME
    pendientes: list[RasterJob] = []

    for job in jobs:
        destino = job.ruta(rasters_capa)
        if not overwrite and raster_valido(destino, job.malla):
            resumen.omitidos += 1
            registro = _registro_raster(job, rasters_capa)
            registro.update({"status": "skipped"})
            append_manifest(manifest_path, registro)
            continue
        if destino.exists() and not overwrite:
            LOGGER.warning("Reemplazando GeoTIFF inválido o desalineado: %s", destino)
        pendientes.append(job)

    LOGGER.info(
        "%d rásteres seleccionados: %d pendientes, %d ya completos",
        len(jobs),
        len(pendientes),
        resumen.omitidos,
    )
    futuros: dict[Future[ResultadoRaster], RasterJob] = {}
    iterador = iter(pendientes)
    stop_event = Event()
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="covariables")

    def enviar_siguiente() -> bool:
        try:
            job = next(iterador)
        except StopIteration:
            return False
        futuro = executor.submit(
            descargar_raster,
            job,
            region,
            rasters_capa,
            max_attempts,
            stop_event=stop_event,
        )
        futuros[futuro] = job
        return True

    try:
        for _ in range(min(workers, len(pendientes))):
            enviar_siguiente()

        posicion = 0
        while futuros:
            terminados, _ = wait(futuros, return_when=FIRST_COMPLETED)
            for futuro in terminados:
                posicion += 1
                job = futuros.pop(futuro)
                registro = _registro_raster(job, rasters_capa)
                try:
                    resultado = futuro.result()
                except ErrorDescargaRaster as exc:
                    resumen.fallidos += 1
                    registro.update(
                        {"status": "failed", "attempts": exc.attempts, "error": str(exc.cause)}
                    )
                    append_manifest(manifest_path, registro)
                    LOGGER.error("Falló %s: %s", job.stem, exc.cause)
                except Exception as exc:
                    resumen.fallidos += 1
                    registro.update({"status": "failed", "attempts": None, "error": str(exc)})
                    append_manifest(manifest_path, registro)
                    LOGGER.exception("Fallo inesperado en %s", job.stem)
                else:
                    resumen.completados += 1
                    registro.update(
                        {
                            "status": "completed",
                            "attempts": resultado.attempts,
                            "bytes": resultado.bytes_escritos,
                            "duration_seconds": round(resultado.duration_seconds, 3),
                        }
                    )
                    append_manifest(manifest_path, registro)
                    LOGGER.info(
                        "Completado %s: %.1f MB en %.1fs (%d/%d pendientes)",
                        job.stem,
                        resultado.bytes_escritos / 1e6,
                        resultado.duration_seconds,
                        posicion,
                        len(pendientes),
                    )
                enviar_siguiente()
    except BaseException:
        stop_event.set()
        for futuro in futuros:
            futuro.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
    return resumen


def configuracion_capa(layer: str, qa_max: int) -> dict[str, Any]:
    config: dict[str, Any] = {
        "covariates_version": COVARIATES_VERSION,
        "layer": layer,
        "malla": {
            "origen_lon": ORIGEN_LON,
            "origen_lat": ORIGEN_LAT,
            "pasos_deg": sorted(ETIQUETAS_MALLA.values()),
        },
        "region_asset": COUNTRY_ASSET,
        "region_filter": {COUNTRY_PROPERTY: COUNTRY_NAME},
        "nodata_sentinel": NODATA_SENTINEL,
        "formato": "GEO_TIFF",
    }
    if layer == "dem":
        config.update(
            {
                "dataset": DEM_DATASET,
                "banda": DEM_BAND,
                "reductores_0p01": list(REDUCTORES_DEM_0P01),
                "reductores_0p06": list(REDUCTORES_DEM_0P06),
            }
        )
    elif layer == "albedo_swir":
        config.update(
            {
                "dataset": MODIS_DATASET,
                "bandas": sorted(MODIS_BANDAS.values()),
                "qa_banda": MODIS_QA_BAND,
                "qa_max": qa_max,
                "escala": MODIS_ESCALA,
                "estadisticas": ["media de días QA-válidos por mes/año", "count de días válidos"],
            }
        )
    else:
        raise CollectionError(f"capa desconocida: {layer}")
    return config


# ---------------------------------------------------------------------------
# Muestreo local: GeoTIFF → parquet en los centros de píxel de la malla CH4
# ---------------------------------------------------------------------------


def cargar_malla_ch4(covariables_dir: Path, csv_path: Path) -> pd.DataFrame:
    """Coordenadas únicas de la malla CH4, cacheadas en parquet tras la primera lectura."""
    cache = covariables_dir / ARCHIVO_MALLA_CH4
    if cache.is_file():
        return pd.read_parquet(cache)
    if not csv_path.is_file():
        raise CollectionError(f"no existe {csv_path}; se necesita para construir la malla CH4")
    LOGGER.info("Construyendo la malla CH4 desde %s (solo la primera vez)", csv_path.name)
    columnas = pd.read_csv(csv_path, usecols=["longitude", "latitude"])
    malla = redondear_coords(columnas).drop_duplicates()
    malla = malla.sort_values(["latitude", "longitude"], ascending=[False, True])
    malla = malla.reset_index(drop=True)
    covariables_dir.mkdir(parents=True, exist_ok=True)
    write_parquet_atomic(malla, cache)
    write_json_atomic(
        cache.with_suffix(".json"),
        {
            "fuente": csv_path.name,
            "definicion": "coordenadas únicas (centros de píxel) redondeadas a 5 decimales",
            "filas": len(malla),
            "generado_utc": datetime.now(UTC).isoformat(),
        },
    )
    LOGGER.info("Malla CH4: %d píxeles", len(malla))
    return malla


def muestrear_en(path: Path, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Valores del ráster en los centros de píxel; indexación directa por estar alineado."""
    with rasterio.open(path) as src:
        datos = src.read(1).astype("float64")
        transform = src.transform
    if transform.b != 0 or transform.d != 0 or transform.e >= 0:
        raise CollectionError(f"{path.name} tiene una transformación no soportada: {transform}")
    desfase = (transform.c - ORIGEN_LON) / transform.a
    if abs(desfase - round(desfase)) > 1e-6:
        LOGGER.warning("%s no está alineado con el origen harp (desfase %.6f)", path.name, desfase)
    columnas = np.floor((lon - transform.c) / transform.a).astype("int64")
    filas = np.floor((transform.f - lat) / -transform.e).astype("int64")
    valores = np.full(lon.shape, np.nan)
    dentro = (
        (filas >= 0) & (filas < datos.shape[0]) & (columnas >= 0) & (columnas < datos.shape[1])
    )
    valores[dentro] = datos[filas[dentro], columnas[dentro]]
    valores[valores <= UMBRAL_NODATA] = np.nan
    return valores


def actualizar_estaticas(
    covariables_dir: Path,
    malla_df: pd.DataFrame,
    nuevas: pd.DataFrame,
    grupo: str,
    metadatos: dict[str, Any],
) -> Path:
    """Añade o reemplaza columnas en estaticas_0p01.parquet sin tocar las demás."""
    destino = covariables_dir / ARCHIVO_ESTATICAS
    nuevo = pd.concat(
        [malla_df[["longitude", "latitude"]].reset_index(drop=True), nuevas.reset_index(drop=True)],
        axis=1,
    )
    if destino.is_file():
        existente = redondear_coords(pd.read_parquet(destino))
        repetidas = [c for c in existente.columns if c in nuevas.columns]
        existente = existente.drop(columns=repetidas)
        combinado = existente.merge(nuevo, on=["longitude", "latitude"], how="outer")
    else:
        combinado = nuevo
    combinado = combinado.sort_values(["latitude", "longitude"], ascending=[False, True])
    combinado = combinado.reset_index(drop=True)
    covariables_dir.mkdir(parents=True, exist_ok=True)
    write_parquet_atomic(combinado, destino)

    ruta_json = destino.with_suffix(".json")
    payload: dict[str, Any] = {}
    if ruta_json.is_file():
        try:
            payload = json.loads(ruta_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("No se pudo leer %s; se regenera", ruta_json.name)
            payload = {}
    payload.setdefault(
        "malla",
        {
            "origen_lon": ORIGEN_LON,
            "origen_lat": ORIGEN_LAT,
            "paso_deg": PASO_0P01,
            "coordenadas": "centros de píxel de la malla CH4, redondeados a 5 decimales",
        },
    )
    payload.setdefault("variables", {})[grupo] = metadatos
    write_json_atomic(ruta_json, payload)
    LOGGER.info(
        "%s actualizado: %d filas, columnas nuevas %s",
        destino.name,
        len(combinado),
        list(nuevas.columns),
    )
    return destino


def construir_estaticas_dem(
    rasters_capa: Path, covariables_dir: Path, malla_df: pd.DataFrame
) -> None:
    """Muestrea los GeoTIFF del DEM y escribe las columnas del plan 01."""
    faltantes = [a for a in COLUMNAS_DEM.values() if not (rasters_capa / a).is_file()]
    if faltantes:
        raise CollectionError(f"faltan GeoTIFF del DEM en {rasters_capa}: {faltantes}")
    lon = malla_df["longitude"].to_numpy("float64")
    lat = malla_df["latitude"].to_numpy("float64")
    columnas: dict[str, np.ndarray] = {}
    for columna, archivo in COLUMNAS_DEM.items():
        columnas[columna] = muestrear_en(rasters_capa / archivo, lon, lat)

    fraccion_sin_dato = float(np.isnan(columnas["elev_m"]).mean())
    if fraccion_sin_dato > UMBRAL_FRACCION_SIN_DEM:
        raise CollectionError(
            f"{fraccion_sin_dato:.1%} de la malla CH4 sin dato GLO30; "
            "revisar la alineación de la malla antes de continuar"
        )
    relleno = {}
    for columna in COLUMNAS_DEM:
        sin_dato = np.isnan(columnas[columna])
        relleno[columna] = int(sin_dato.sum())
        columnas[columna] = np.nan_to_num(columnas[columna], nan=0.0)
    if any(relleno.values()):
        LOGGER.warning(
            "Píxeles sin dato GLO30 (océano/costa) rellenados con 0 m: %s", relleno
        )

    nuevas = pd.DataFrame(columnas)
    nuevas["elev_res_nativa_m"] = np.int16(DEM_RES_NATIVA_M)
    nuevas["celda_0p06_id"] = celda_0p06_id(lon, lat)
    metadatos = {
        "fuente": DEM_DATASET,
        "banda": DEM_BAND,
        "resolucion_nativa_m": DEM_RES_NATIVA_M,
        "columnas": {
            "elev_m": "media GLO30 en la celda de 0.01°",
            "elev_std_1km": "desviación típica de la elevación en 0.01°",
            "elev_std_7km": "desviación típica en 0.06° (huella ~7 km del sondeo CH4)",
            "elev_min_7km": "mínimo en 0.06°",
            "elev_max_7km": "máximo en 0.06°",
            "celda_0p06_id": "fila·100000+columna de la celda 0.06° (agrupar errores, plan 03)",
        },
        "remuestreo": (
            "reduceResolution sobre el mosaico GLO30 en la malla harp; "
            "muestreo local en centros de píxel"
        ),
        "vertical": "altura sobre el geoide EGM2008",
        "relleno_oceano_0m": relleno,
        "licencia": "Copernicus DEM GLO-30 (ESA/Airbus): uso libre con atribución",
        "archivos_raster": sorted(COLUMNAS_DEM.values()),
        "descargado_utc": datetime.now(UTC).isoformat(),
    }
    actualizar_estaticas(covariables_dir, malla_df, nuevas, "dem_glo30", metadatos)


def _periodos_albedo(directorio: Path, patron: str) -> list[str]:
    """Sufijos de periodo (YYYY o YYYY-MM) de los GeoTIFF BSA a 0.01° presentes."""
    periodos = []
    for ruta in sorted(directorio.glob("albedo_bsa_0p01_*.tif")):
        sufijo = ruta.stem.rsplit("_", 1)[-1]
        if re.fullmatch(patron, sufijo):
            periodos.append(sufijo)
    return periodos


def _metadatos_albedo(qa_max: int, extra: dict[str, Any]) -> dict[str, Any]:
    metadatos = {
        "fuente": MODIS_DATASET,
        "bandas": {"albedo_swir": MODIS_BANDAS["bsa"], "albedo_swir_wsa": MODIS_BANDAS["wsa"]},
        "resolucion_nativa_m": MODIS_RES_NATIVA_M,
        "mascara_calidad": f"{MODIS_QA_BAND} <= {qa_max}",
        "escala_aplicada": MODIS_ESCALA,
        "remuestreo": (
            "media de días QA-válidos y reduceResolution(mean) en la malla harp; "
            "muestreo local en centros de píxel"
        ),
        "advertencia": (
            "MCD43A3 banda 7 es 2.1 µm: proxy espectral cercano, no el albedo de 2.3 µm "
            "que usa el retrieval de CH4 (plan 02 §7)"
        ),
        "licencia": "NASA LP DAAC, dominio público",
        "descargado_utc": datetime.now(UTC).isoformat(),
    }
    metadatos.update(extra)
    return metadatos


def construir_estaticas_albedo(
    rasters_capa: Path, covariables_dir: Path, malla_df: pd.DataFrame, qa_max: int
) -> None:
    """Columnas albedo_swir_<año> (BSA, y WSA si existe) desde las medias anuales en disco."""
    anual = rasters_capa / "anual"
    anios = _periodos_albedo(anual, r"\d{4}") if anual.is_dir() else []
    if not anios:
        LOGGER.warning("No hay medias anuales de albedo en %s; se omiten las estáticas", anual)
        return
    lon = malla_df["longitude"].to_numpy("float64")
    lat = malla_df["latitude"].to_numpy("float64")
    columnas: dict[str, np.ndarray] = {}
    for anio in anios:
        columnas[f"albedo_swir_{anio}"] = muestrear_en(
            anual / f"albedo_bsa_0p01_{anio}.tif", lon, lat
        )
        ruta_wsa = anual / f"albedo_wsa_0p01_{anio}.tif"
        if ruta_wsa.is_file():
            columnas[f"albedo_swir_wsa_{anio}"] = muestrear_en(ruta_wsa, lon, lat)
    for columna, valores in columnas.items():
        nulos = int(np.isnan(valores).sum())
        if nulos:
            LOGGER.info("%s: %d píxeles sin dato (océano o sin inversión BRDF)", columna, nulos)
    nuevas = pd.DataFrame(columnas)
    nuevas["albedo_swir_res_nativa_m"] = np.int16(MODIS_RES_NATIVA_M)
    metadatos = _metadatos_albedo(qa_max, {"anios": [int(a) for a in anios]})
    actualizar_estaticas(covariables_dir, malla_df, nuevas, "albedo_swir_anual", metadatos)


def construir_mensuales_albedo(
    rasters_capa: Path, covariables_dir: Path, malla_df: pd.DataFrame, qa_max: int
) -> None:
    """Reconstruye mensuales/albedo_swir_0p01.parquet desde todos los meses en disco."""
    mensual = rasters_capa / "mensual"
    meses = _periodos_albedo(mensual, r"\d{4}-\d{2}") if mensual.is_dir() else []
    if not meses:
        LOGGER.warning("No hay meses de albedo en %s; se omite el parquet mensual", mensual)
        return
    lon = malla_df["longitude"].to_numpy("float64")
    lat = malla_df["latitude"].to_numpy("float64")
    destino_dir = covariables_dir / DIRECTORIO_MENSUALES
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / "albedo_swir_0p01.parquet"
    temporal = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")

    incompletos: list[str] = []
    filas_totales = 0
    escritor: pq.ParquetWriter | None = None
    try:
        for periodo in meses:
            rutas = {
                tipo: mensual / f"albedo_{tipo}_0p01_{periodo}.tif" for tipo in TIPOS_ALBEDO
            }
            if not all(ruta.is_file() for ruta in rutas.values()):
                incompletos.append(periodo)
                continue
            bsa = muestrear_en(rutas["bsa"], lon, lat)
            wsa = muestrear_en(rutas["wsa"], lon, lat)
            nobs = np.nan_to_num(muestrear_en(rutas["nobs"], lon, lat), nan=0.0)
            conservar = ~(np.isnan(bsa) & np.isnan(wsa))
            n = int(conservar.sum())
            anio, mes = int(periodo[:4]), int(periodo[5:7])
            tabla = pa.table(
                {
                    "longitude": lon[conservar],
                    "latitude": lat[conservar],
                    "year": np.full(n, anio, dtype="int16"),
                    "month": np.full(n, mes, dtype="int8"),
                    "albedo_swir": bsa[conservar].astype("float32"),
                    "albedo_swir_wsa": wsa[conservar].astype("float32"),
                    "albedo_swir_n_obs": nobs[conservar].astype("float32"),
                    "albedo_swir_res_nativa_m": np.full(
                        n, MODIS_RES_NATIVA_M, dtype="int16"
                    ),
                }
            )
            if escritor is None:
                escritor = pq.ParquetWriter(temporal, tabla.schema, compression="snappy")
            escritor.write_table(tabla)
            filas_totales += n
    finally:
        if escritor is not None:
            escritor.close()
    if escritor is None:
        temporal.unlink(missing_ok=True)
        raise CollectionError(f"ningún mes completo (bsa+wsa+nobs) en {mensual}")
    os.replace(temporal, destino)
    if incompletos:
        LOGGER.warning("Meses con GeoTIFF incompletos, excluidos del parquet: %s", incompletos)
    write_json_atomic(
        destino.with_suffix(".json"),
        _metadatos_albedo(
            qa_max,
            {
                "meses": [m for m in meses if m not in incompletos],
                "meses_incompletos": incompletos,
                "filas": filas_totales,
                "politica_filas": (
                    "se descartan los píxeles-mes sin BSA ni WSA (océano o sin inversión); "
                    "albedo_swir_n_obs es 0 cuando ningún día pasó la máscara"
                ),
            },
        ),
    )
    LOGGER.info(
        "%s escrito: %d filas en %d meses",
        destino.name,
        filas_totales,
        len(meses) - len(incompletos),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    default_project = os.environ.get("EE_PROJECT")
    parser = argparse.ArgumentParser(
        description=(
            "Descarga covariables de Earth Engine como GeoTIFF en la malla harp "
            "(0.01° y 0.06°) recortados a Colombia y las muestrea en la malla CH4."
        )
    )
    parser.add_argument(
        "--project",
        default=default_project,
        help="Proyecto de Google Cloud registrado en Earth Engine (o variable EE_PROJECT).",
    )
    parser.add_argument("--layer", required=True, choices=("dem", "albedo_swir"))
    parser.add_argument(
        "--start", default="2019-01", help="Primer mes YYYY-MM (solo capas temporales)."
    )
    parser.add_argument(
        "--end", default="2026-01", help="Mes final exclusivo YYYY-MM (solo capas temporales)."
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2022, 2024],
        help="Años de las medias anuales que van a las columnas estáticas (plan 02).",
    )
    parser.add_argument(
        "--rasters-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "covariables",
        help="Raíz de los GeoTIFF intermedios (se crea un subdirectorio por capa).",
    )
    parser.add_argument(
        "--covariables-dir",
        type=Path,
        default=RUTA_COVARIABLES,
        help="Directorio de los parquet de covariables del análisis.",
    )
    parser.add_argument(
        "--ch4-csv",
        type=Path,
        default=CH4_CSV,
        help="CSV con la malla CH4 (solo se lee si no existe la malla cacheada).",
    )
    parser.add_argument("--workers", type=worker_count, default=8)
    parser.add_argument("--max-attempts", type=positive_int, default=5)
    parser.add_argument(
        "--qa-max",
        type=int,
        choices=(0, 1),
        default=0,
        help="Calidad MCD43A3 máxima aceptada: 0 solo inversión BRDF completa (default).",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Volver a descargar rásteres válidos."
    )
    parser.add_argument(
        "--skip-sample", action="store_true", help="Solo descargar; no escribir parquet."
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="No descargar; reconstruir los parquet desde los GeoTIFF ya presentes.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Listar los rásteres pendientes sin descargar."
    )
    parser.add_argument("--authenticate", action="store_true")
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    return parser


def _run_metadata(
    args: argparse.Namespace, started_at: datetime, resumen: ResumenRasters
) -> dict[str, Any]:
    return {
        "covariates_version": COVARIATES_VERSION,
        "layer": args.layer,
        "project": args.project,
        "start": args.start,
        "end_exclusive": args.end,
        "years": args.years,
        "qa_max": args.qa_max,
        "workers": args.workers,
        "max_attempts": args.max_attempts,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "summary": asdict(resumen),
        "earthengine_api_version": ee.__version__,
        "python_version": sys.version.split()[0],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        if args.skip_sample and args.sample_only:
            raise CollectionError("--skip-sample y --sample-only son excluyentes")
        rasters_capa = args.rasters_dir / args.layer
        resumen: ResumenRasters | None = None

        if not args.sample_only:
            if args.project is None:
                raise CollectionError("falta --project (o la variable EE_PROJECT)")
            if args.layer == "albedo_swir":
                meses = rango_meses(args.start, args.end)
            initialize_earth_engine(args.project, args.authenticate)
            region = colombia_geometry()
            mallas = mallas_colombia(region)
            for malla in mallas.values():
                LOGGER.info(
                    "Malla %s: %d × %d px desde (%.2f, %.2f)",
                    malla.etiqueta,
                    malla.ancho,
                    malla.alto,
                    malla.lon_oeste,
                    malla.lat_norte,
                )
            if args.layer == "dem":
                jobs = jobs_dem(mallas)
            else:
                jobs = jobs_albedo(mallas, meses, args.years, args.qa_max)

            if args.dry_run:
                pendientes = [
                    job
                    for job in jobs
                    if args.overwrite or not raster_valido(job.ruta(rasters_capa), job.malla)
                ]
                LOGGER.info(
                    "%d rásteres definidos, %d pendientes de descargar",
                    len(jobs),
                    len(pendientes),
                )
                for job in pendientes:
                    ruta = job.ruta(rasters_capa).relative_to(args.rasters_dir)
                    LOGGER.info("pendiente: %s", ruta)
                return 0

            with lock_output_directory(rasters_capa):
                prepare_output_directory(
                    rasters_capa, configuracion_capa(args.layer, args.qa_max), data_glob="*.tif"
                )
                started_at = datetime.now(UTC)
                resumen = ejecutar_descargas(
                    jobs=jobs,
                    region=region,
                    rasters_capa=rasters_capa,
                    workers=args.workers,
                    max_attempts=args.max_attempts,
                    overwrite=args.overwrite,
                )
                write_json_atomic(
                    rasters_capa / LAST_RUN_FILENAME, _run_metadata(args, started_at, resumen)
                )
            LOGGER.info(
                "Descarga: %d completados, %d omitidos, %d fallidos",
                resumen.completados,
                resumen.omitidos,
                resumen.fallidos,
            )
            if resumen.fallidos:
                LOGGER.error(
                    "Hay descargas fallidas; no se muestrea. Reejecuta el mismo comando "
                    "para reintentar solo lo pendiente."
                )
                return 1

        if not args.skip_sample:
            args.covariables_dir.mkdir(parents=True, exist_ok=True)
            malla_df = cargar_malla_ch4(args.covariables_dir, args.ch4_csv)
            if args.layer == "dem":
                construir_estaticas_dem(rasters_capa, args.covariables_dir, malla_df)
            else:
                construir_estaticas_albedo(
                    rasters_capa, args.covariables_dir, malla_df, args.qa_max
                )
                construir_mensuales_albedo(
                    rasters_capa, args.covariables_dir, malla_df, args.qa_max
                )
    except CollectionError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.error("Interrumpido; los GeoTIFF completos se reutilizan en la siguiente corrida")
        return 130
    except Exception:
        LOGGER.exception("Fallo inesperado del recolector de covariables")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
