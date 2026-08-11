#!/usr/bin/env python3
"""Download Sentinel-5P methane observations over Colombia from Earth Engine."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event
from typing import Any, Callable, Iterator, Sequence

import ee
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DATASET_ID = "COPERNICUS/S5P/OFFL/L3_CH4"
DATASET_START = date(2019, 2, 8)
PRIMARY_BAND = "CH4_column_volume_mixing_ratio_dry_air_bias_corrected"
DEFAULT_BANDS = (
    "CH4_column_volume_mixing_ratio_dry_air",
    PRIMARY_BAND,
    "CH4_column_volume_mixing_ratio_dry_air_uncertainty",
    "aerosol_height",
    "aerosol_optical_depth",
    "sensor_azimuth_angle",
    "sensor_zenith_angle",
    "solar_azimuth_angle",
    "solar_zenith_angle",
)
COUNTRY_ASSET = "FAO/GAUL_SIMPLIFIED_500m/2015/level0"
COUNTRY_PROPERTY = "ADM0_NAME"
COUNTRY_NAME = "Colombia"
HIGH_VOLUME_URL = "https://earthengine-highvolume.googleapis.com"
COLLECTOR_VERSION = 2
CONFIG_FILENAME = "_collection_config.json"
MANIFEST_FILENAME = "_manifest.jsonl"
LAST_RUN_FILENAME = "_last_run.json"
LOCK_FILENAME = ".collector.lock"

METADATA_SELECTORS = (
    "system:index",
    "system:time_start",
    "ORBIT",
    "PRODUCT_ID",
    "PROCESSING_STATUS",
    "PRODUCT_QUALITY",
    "PROCESSOR_VERSION",
    "ALGORITHM_VERSION",
    "HARP_VERSION",
    "SPATIAL_RESOLUTION",
)

STRING_METADATA_COLUMNS = (
    "product_id",
    "processing_status",
    "product_quality",
    "processor_version",
    "algorithm_version",
    "spatial_resolution",
)

LOGGER = logging.getLogger("collect_gee_colombia")


class CollectionError(RuntimeError):
    """Base error for an invalid configuration or failed collection run."""


class ImageCollectionError(CollectionError):
    """Error raised after an image could not be collected."""

    def __init__(self, job: ImageJob, attempts: int, cause: Exception) -> None:
        super().__init__(f"{job.index}: {cause}")
        self.job = job
        self.attempts = attempts
        self.cause = cause


@dataclass(frozen=True)
class ImageJob:
    """Metadata required to download one Earth Engine image."""

    index: str
    time_ms: int
    orbit: int | None = None
    product_id: str | None = None
    processing_status: str | None = None
    product_quality: str | None = None
    processor_version: str | None = None
    algorithm_version: str | None = None
    harp_version: int | None = None
    spatial_resolution: str | None = None


@dataclass(frozen=True)
class ImageResult:
    """Result of downloading and writing one image."""

    job: ImageJob
    path: Path
    rows: int
    attempts: int
    duration_seconds: float


@dataclass
class CollectionSummary:
    """Counters for a complete collection invocation."""

    total_jobs: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    rows: int = 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def worker_count(value: str) -> int:
    parsed = positive_int(value)
    if parsed > 40:
        raise argparse.ArgumentTypeError("must not exceed the default GEE limit of 40")
    return parsed


def parse_date_range(start: str, end: str) -> tuple[date, date]:
    """Parse and validate an Earth Engine half-open date range."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", end
    ):
        raise CollectionError("dates must use YYYY-MM-DD")
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise CollectionError("dates must use YYYY-MM-DD") from exc
    if start_date >= end_date:
        raise CollectionError("--end must be later than --start (end is exclusive)")
    return start_date, end_date


def build_parser() -> argparse.ArgumentParser:
    default_project = os.environ.get("EE_PROJECT")
    parser = argparse.ArgumentParser(
        description=(
            "Download native 0.01 degree Sentinel-5P OFFL methane pixels over Colombia "
            "into resumable Parquet partitions."
        )
    )
    parser.add_argument(
        "--project",
        default=default_project,
        required=default_project is None,
        help="Google Cloud project registered for Earth Engine (or set EE_PROJECT).",
    )
    parser.add_argument("--start", required=True, help="First UTC date, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="Exclusive UTC end date, YYYY-MM-DD.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "s5p_ch4",
        help="Root directory for Parquet partitions and manifests.",
    )
    parser.add_argument(
        "--bands",
        nargs="+",
        default=list(DEFAULT_BANDS),
        help="S5P bands to collect. The bias-corrected CH4 band is mandatory.",
    )
    parser.add_argument("--workers", type=worker_count, default=8)
    parser.add_argument("--page-size", type=positive_int, default=5_000)
    parser.add_argument("--tile-scale", type=positive_int, default=2)
    parser.add_argument("--max-attempts", type=positive_int, default=5)
    parser.add_argument(
        "--max-images",
        type=positive_int,
        help="Limit the number of images, useful for a live smoke test.",
    )
    parser.add_argument(
        "--nominal-only",
        action="store_true",
        help="Keep only images with nominal processing status and product quality.",
    )
    parser.add_argument(
        "--authenticate",
        action="store_true",
        help="Run the interactive Earth Engine authentication flow before initializing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download valid image files that already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the matching image count without downloading data.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def initialize_earth_engine(project: str, authenticate: bool = False) -> None:
    """Authenticate when requested and initialize the high-volume endpoint."""
    if authenticate:
        ee.Authenticate()
    try:
        ee.Initialize(project=project, url=HIGH_VOLUME_URL)
    except Exception as exc:
        raise CollectionError(
            "Earth Engine initialization failed. Check --project and credentials; "
            "run again with --authenticate if needed."
        ) from exc


def colombia_geometry() -> ee.Geometry:
    """Return the public GAUL level-0 geometry for Colombia."""
    countries = ee.FeatureCollection(COUNTRY_ASSET)
    colombia = countries.filter(ee.Filter.eq(COUNTRY_PROPERTY, COUNTRY_NAME)).first()
    return ee.Feature(colombia).geometry()


def build_collection(
    region: ee.Geometry,
    start: date,
    end: date,
    bands: Sequence[str],
    nominal_only: bool,
) -> ee.ImageCollection:
    """Build the smallest possible source collection before extraction."""
    collection = (
        ee.ImageCollection(DATASET_ID)
        .filterDate(start.isoformat(), end.isoformat())
        .filterBounds(region)
        .select(list(bands))
        .sort("system:time_start")
    )
    if nominal_only:
        collection = collection.filter(ee.Filter.eq("PROCESSING_STATUS", "Nominal")).filter(
            ee.Filter.eq("PRODUCT_QUALITY", "Nominal")
        )
    return collection


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def image_job_from_row(row: Sequence[Any]) -> ImageJob:
    """Convert one reduceColumns metadata tuple to a typed image job."""
    values = list(row) + [None] * (len(METADATA_SELECTORS) - len(row))
    if values[0] is None or values[1] is None:
        raise CollectionError(f"image metadata is missing an index or timestamp: {row!r}")
    return ImageJob(
        index=str(values[0]),
        time_ms=int(values[1]),
        orbit=_optional_int(values[2]),
        product_id=_optional_str(values[3]),
        processing_status=_optional_str(values[4]),
        product_quality=_optional_str(values[5]),
        processor_version=_optional_str(values[6]),
        algorithm_version=_optional_str(values[7]),
        harp_version=_optional_int(values[8]),
        spatial_resolution=_optional_str(values[9]),
    )


def list_image_jobs(collection: ee.ImageCollection) -> list[ImageJob]:
    """Fetch only compact image metadata, never image pixels, with getInfo()."""
    optional_count = len(METADATA_SELECTORS) - 2
    rows = (
        collection.reduceColumns(
            reducer=ee.Reducer.toList(len(METADATA_SELECTORS), optional_count),
            selectors=list(METADATA_SELECTORS),
        )
        .get("list")
        .getInfo()
    )
    jobs = [image_job_from_row(row) for row in (rows or [])]
    jobs.sort(key=lambda job: (job.time_ms, job.index))
    if len({job.index for job in jobs}) != len(jobs):
        raise CollectionError("Earth Engine returned duplicate system:index values")
    return jobs


def fetch_image_dataframe(
    job: ImageJob,
    region: ee.Geometry,
    bands: Sequence[str],
    page_size: int,
    tile_scale: int,
) -> pd.DataFrame:
    """Sample one sparse S5P image and fetch all result pages as a DataFrame."""
    image = ee.Image(f"{DATASET_ID}/{job.index}").select(list(bands))
    primary = image.select(PRIMARY_BAND)
    validity_names = [validity_column(position) for position in range(len(bands))]
    validity = image.mask().unmask(0).rename(validity_names)
    sample_image = (
        image.unmask(0)
        .addBands(validity)
        .addBands(ee.Image.pixelLonLat())
        .updateMask(primary.mask())
    )
    samples = sample_image.sample(
        region=region,
        projection=primary.projection(),
        dropNulls=True,
        tileScale=tile_scale,
        geometries=False,
    )
    result = ee.data.computeFeatures(
        {
            "expression": samples,
            "fileFormat": "PANDAS_DATAFRAME",
            "pageSize": page_size,
            "workloadTag": "s5p-ch4-colombia",
        }
    )
    if not isinstance(result, pd.DataFrame):
        raise CollectionError(f"unexpected computeFeatures result for {job.index}")
    return result


def validity_column(position: int) -> str:
    return f"__valid_{position}"


def output_columns(bands: Sequence[str]) -> list[str]:
    return [
        "id",
        "longitude",
        "latitude",
        "time",
        "date",
        "date_colombia",
        *bands,
        "orbit",
        "product_id",
        "processing_status",
        "product_quality",
        "processor_version",
        "algorithm_version",
        "harp_version",
        "spatial_resolution",
    ]


def _constant_series(value: Any, rows: int, dtype: str) -> pd.Series:
    return pd.Series([value] * rows, dtype=dtype)


def normalize_dataframe(
    frame: pd.DataFrame, job: ImageJob, bands: Sequence[str]
) -> pd.DataFrame:
    """Apply a stable, narrow schema without modifying scientific values."""
    scientific_columns = ["longitude", "latitude", *bands]
    if frame.empty:
        normalized = pd.DataFrame(
            {column: pd.Series(dtype="float64") for column in scientific_columns}
        )
    else:
        validity_columns = [validity_column(position) for position in range(len(bands))]
        required_columns = {*scientific_columns, *validity_columns}
        missing = sorted(required_columns.difference(frame.columns))
        if missing:
            raise CollectionError(f"{job.index} is missing sampled columns: {missing}")

        normalized = frame[scientific_columns].copy()
        try:
            for column in scientific_columns:
                normalized[column] = pd.to_numeric(normalized[column], errors="raise")
            for position, band in enumerate(bands):
                mask_column = validity_column(position)
                valid = pd.to_numeric(frame[mask_column], errors="raise").gt(0)
                normalized.loc[~valid, band] = pd.NA
        except (TypeError, ValueError) as exc:
            raise CollectionError(f"{job.index} contains non-numeric sampled values") from exc

        normalized = normalized.dropna(subset=["longitude", "latitude", PRIMARY_BAND])
        normalized = normalized.reset_index(drop=True).astype("float64")

    rows = len(normalized)
    utc_timestamp = pd.to_datetime(job.time_ms, unit="ms", utc=True)
    colombia_timestamp = utc_timestamp.tz_convert("America/Bogota")
    normalized["id"] = _constant_series(job.index, rows, "string")
    normalized["time"] = _constant_series(job.time_ms, rows, "int64")
    normalized["date"] = _constant_series(utc_timestamp, rows, "datetime64[ns, UTC]")
    normalized["date_colombia"] = _constant_series(
        colombia_timestamp, rows, "datetime64[ns, America/Bogota]"
    )
    normalized["orbit"] = _constant_series(job.orbit, rows, "Int64")
    normalized["harp_version"] = _constant_series(job.harp_version, rows, "Int64")
    for column in STRING_METADATA_COLUMNS:
        normalized[column] = _constant_series(getattr(job, column), rows, "string")

    return normalized[output_columns(bands)]


def expected_parquet_schema(bands: Sequence[str]) -> pa.Schema:
    """Build the exact Arrow schema emitted by the active pandas/PyArrow versions."""
    empty = normalize_dataframe(pd.DataFrame(), ImageJob(index="schema", time_ms=0), bands)
    return pa.Schema.from_pandas(empty, preserve_index=False).remove_metadata()


def image_file_stem(index: str) -> str:
    """Build a portable and collision-resistant filename from system:index."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", index).strip("._") or "image"
    digest = hashlib.sha256(index.encode("utf-8")).hexdigest()[:10]
    return f"{safe[:120]}-{digest}"


def output_path_for_job(output: Path, job: ImageJob) -> Path:
    timestamp = datetime.fromtimestamp(job.time_ms / 1000, tz=UTC)
    return (
        output
        / f"year={timestamp.year:04d}"
        / f"month={timestamp.month:02d}"
        / f"{image_file_stem(job.index)}.parquet"
    )


def write_parquet_atomic(frame: pd.DataFrame, destination: Path) -> None:
    """Write a complete Parquet file before atomically exposing it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        frame.to_parquet(temporary, engine="pyarrow", compression="snappy", index=False)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def existing_parquet_rows(path: Path, expected_schema: pa.Schema) -> int | None:
    """Return row count for a valid existing output, otherwise None."""
    if not path.is_file():
        return None
    try:
        parquet = pq.ParquetFile(path)
        actual_schema = parquet.schema_arrow.remove_metadata()
        if not actual_schema.equals(expected_schema, check_metadata=False):
            return None
        return parquet.metadata.num_rows
    except (OSError, ValueError):
        return None


def collection_config(bands: Sequence[str], nominal_only: bool) -> dict[str, Any]:
    return {
        "collector_version": COLLECTOR_VERSION,
        "dataset": DATASET_ID,
        "bands": list(bands),
        "primary_band": PRIMARY_BAND,
        "region_asset": COUNTRY_ASSET,
        "region_filter": {COUNTRY_PROPERTY: COUNTRY_NAME},
        "grid": "native-primary-band-projection",
        "mask_policy": "primary-band-valid-with-nullable-auxiliary-bands",
        "nominal_only": nominal_only,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_output_directory(output: Path, config: dict[str, Any]) -> None:
    """Prevent datasets with incompatible extraction settings from mixing."""
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / CONFIG_FILENAME
    if config_path.exists():
        try:
            with config_path.open(encoding="utf-8") as stream:
                existing = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise CollectionError(f"cannot read {config_path}") from exc
        if existing != config:
            raise CollectionError(
                f"{output} contains a different collection configuration; "
                "choose another --output directory"
            )
        return
    if next(output.rglob("*.parquet"), None) is not None:
        raise CollectionError(f"{output} contains Parquet files but no {CONFIG_FILENAME}")
    write_json_atomic(config_path, config)


@contextmanager
def lock_output_directory(output: Path) -> Iterator[None]:
    """Prevent concurrent collectors from writing into the same dataset root."""
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / LOCK_FILENAME
    with lock_path.open("a+", encoding="utf-8") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CollectionError(f"another collector is using {output}") from exc
        stream.seek(0)
        stream.truncate()
        stream.write(f"pid={os.getpid()} started={datetime.now(UTC).isoformat()}\n")
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def append_manifest(path: Path, payload: dict[str, Any]) -> None:
    """Append one auditable job event. The caller serializes all writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        stream.write("\n")
        stream.flush()


def is_retryable_error(error: Exception) -> bool:
    """Classify transient HTTP and network errors without hiding invalid requests."""
    response = getattr(error, "resp", None)
    status = getattr(response, "status", None)
    if status in {429, 500, 502, 503, 504}:
        return True
    if isinstance(error, (ConnectionError, TimeoutError)):
        return True
    message = str(error).lower()
    transient_markers = (
        "429",
        "internal error",
        "connection reset",
        "connection aborted",
        "deadline exceeded",
        "quota exceeded",
        "rate limit",
        "server error",
        "service unavailable",
        "socket timeout",
        "temporarily unavailable",
        "too many concurrent aggregations",
        "timed out",
        "timeout",
    )
    return any(marker in message for marker in transient_markers)


def collect_image(
    job: ImageJob,
    region: ee.Geometry,
    bands: Sequence[str],
    output: Path,
    page_size: int,
    tile_scale: int,
    max_attempts: int,
    sleep: Callable[[float], None] = time.sleep,
    stop_event: Event | None = None,
) -> ImageResult:
    """Fetch, normalize and atomically persist one image with bounded retries."""
    started = time.perf_counter()
    destination = output_path_for_job(output, job)
    for attempt in range(1, max_attempts + 1):
        if stop_event is not None and stop_event.is_set():
            raise CollectionError(f"collection interrupted before fetching {job.index}")
        try:
            raw = fetch_image_dataframe(job, region, bands, page_size, tile_scale)
            normalized = normalize_dataframe(raw, job, bands)
            write_parquet_atomic(normalized, destination)
            return ImageResult(
                job=job,
                path=destination,
                rows=len(normalized),
                attempts=attempt,
                duration_seconds=time.perf_counter() - started,
            )
        except Exception as exc:
            if attempt >= max_attempts or not is_retryable_error(exc):
                raise ImageCollectionError(job, attempt, exc) from exc
            delay = min(60.0, 2.0 ** (attempt - 1)) + random.uniform(0.0, 0.5)
            LOGGER.warning(
                "%s failed on attempt %d/%d; retrying in %.1fs: %s",
                job.index,
                attempt,
                max_attempts,
                delay,
                exc,
            )
            if stop_event is None:
                sleep(delay)
            elif stop_event.wait(delay):
                raise CollectionError(f"collection interrupted while retrying {job.index}")
    raise AssertionError("unreachable")


def _manifest_base(job: ImageJob, output: Path) -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "image_id": job.index,
        "image_time_ms": job.time_ms,
        "path": str(output_path_for_job(output, job).relative_to(output)),
    }


def run_collection(
    jobs: Sequence[ImageJob],
    region: ee.Geometry,
    bands: Sequence[str],
    output: Path,
    workers: int,
    page_size: int,
    tile_scale: int,
    max_attempts: int,
    overwrite: bool,
) -> CollectionSummary:
    """Collect all images while serializing progress records in the main thread."""
    summary = CollectionSummary(total_jobs=len(jobs))
    manifest_path = output / MANIFEST_FILENAME
    required_schema = expected_parquet_schema(bands)
    pending: list[ImageJob] = []

    for job in jobs:
        destination = output_path_for_job(output, job)
        rows = None if overwrite else existing_parquet_rows(destination, required_schema)
        if rows is None:
            if destination.exists() and not overwrite:
                LOGGER.warning("Replacing invalid or incompatible output: %s", destination)
            pending.append(job)
            continue
        summary.skipped += 1
        summary.rows += rows
        record = _manifest_base(job, output)
        record.update({"status": "skipped", "rows": rows})
        append_manifest(manifest_path, record)

    LOGGER.info(
        "%d images selected: %d pending, %d already complete",
        len(jobs),
        len(pending),
        summary.skipped,
    )
    futures: dict[Future[ImageResult], ImageJob] = {}
    pending_iterator = iter(pending)
    stop_event = Event()
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="s5p")

    def submit_next() -> bool:
        try:
            job = next(pending_iterator)
        except StopIteration:
            return False
        future = executor.submit(
            collect_image,
            job,
            region,
            bands,
            output,
            page_size,
            tile_scale,
            max_attempts,
            stop_event=stop_event,
        )
        futures[future] = job
        return True

    try:
        for _ in range(min(workers, len(pending))):
            submit_next()

        position = 0
        while futures:
            completed_futures, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed_futures:
                position += 1
                job = futures.pop(future)
                try:
                    result = future.result()
                except ImageCollectionError as exc:
                    summary.failed += 1
                    record = _manifest_base(job, output)
                    record.update(
                        {
                            "status": "failed",
                            "attempts": exc.attempts,
                            "error": str(exc.cause),
                        }
                    )
                    append_manifest(manifest_path, record)
                    LOGGER.error("Failed %s: %s", job.index, exc.cause)
                except Exception as exc:
                    summary.failed += 1
                    record = _manifest_base(job, output)
                    record.update({"status": "failed", "attempts": None, "error": str(exc)})
                    append_manifest(manifest_path, record)
                    LOGGER.exception("Unexpected failure for %s", job.index)
                else:
                    summary.completed += 1
                    summary.rows += result.rows
                    record = _manifest_base(job, output)
                    record.update(
                        {
                            "status": "completed",
                            "rows": result.rows,
                            "attempts": result.attempts,
                            "duration_seconds": round(result.duration_seconds, 3),
                        }
                    )
                    append_manifest(manifest_path, record)
                    LOGGER.info(
                        "Completed %s: %,d rows in %.1fs (%d/%d pending)",
                        job.index,
                        result.rows,
                        result.duration_seconds,
                        position,
                        len(pending),
                    )
                submit_next()
    except BaseException:
        stop_event.set()
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
    return summary


def _run_metadata(
    args: argparse.Namespace,
    start: date,
    end: date,
    started_at: datetime,
    summary: CollectionSummary,
) -> dict[str, Any]:
    return {
        "collector_version": COLLECTOR_VERSION,
        "dataset": DATASET_ID,
        "project": args.project,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "bands": list(args.bands),
        "workers": args.workers,
        "page_size": args.page_size,
        "tile_scale": args.tile_scale,
        "max_attempts": args.max_attempts,
        "nominal_only": args.nominal_only,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "summary": asdict(summary),
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
        start, end = parse_date_range(args.start, args.end)
        if PRIMARY_BAND not in args.bands:
            raise CollectionError(f"--bands must include {PRIMARY_BAND}")
        if len(args.bands) != len(set(args.bands)):
            raise CollectionError("--bands must not contain duplicates")
        if start < DATASET_START:
            LOGGER.warning(
                "The S5P CH4 collection starts on %s; earlier dates return no images",
                DATASET_START,
            )

        initialize_earth_engine(args.project, args.authenticate)
        region = colombia_geometry()
        collection = build_collection(region, start, end, args.bands, args.nominal_only)
        jobs = list_image_jobs(collection)
        if args.max_images is not None:
            jobs = jobs[: args.max_images]

        LOGGER.info(
            "Found %d S5P images over Colombia for [%s, %s)", len(jobs), start, end
        )
        if args.dry_run:
            return 0

        with lock_output_directory(args.output):
            config = collection_config(args.bands, args.nominal_only)
            prepare_output_directory(args.output, config)
            started_at = datetime.now(UTC)
            summary = run_collection(
                jobs=jobs,
                region=region,
                bands=args.bands,
                output=args.output,
                workers=args.workers,
                page_size=args.page_size,
                tile_scale=args.tile_scale,
                max_attempts=args.max_attempts,
                overwrite=args.overwrite,
            )
            write_json_atomic(
                args.output / LAST_RUN_FILENAME,
                _run_metadata(args, start, end, started_at, summary),
            )
    except CollectionError as exc:
        LOGGER.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        LOGGER.error("Interrupted; completed Parquet files will be reused on the next run")
        return 130
    except Exception:
        LOGGER.exception("Unexpected collector failure")
        return 1

    LOGGER.info(
        "Finished: %d completed, %d skipped, %d failed, %,d rows",
        summary.completed,
        summary.skipped,
        summary.failed,
        summary.rows,
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
