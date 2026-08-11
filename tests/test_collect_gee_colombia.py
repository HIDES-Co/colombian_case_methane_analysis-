from datetime import timedelta
from threading import Event
from types import SimpleNamespace

import pandas as pd
import pytest

from data_collection import collect_gee_colombia as collector


def make_job(**overrides):
    values = {
        "index": "20190208T164037_20190214T182526",
        "time_ms": 1_549_645_332_000,
        "orbit": 7072,
        "product_id": "S5P_OFFL_L2__CH4_test",
        "processing_status": "Nominal",
        "product_quality": "Nominal",
        "processor_version": "2.6.0",
        "algorithm_version": "2.6.0",
        "harp_version": 1900,
        "spatial_resolution": "7x7 km2",
    }
    values.update(overrides)
    return collector.ImageJob(**values)


def test_parse_date_range_is_half_open():
    start, end = collector.parse_date_range("2019-02-08", "2019-02-09")

    assert start.isoformat() == "2019-02-08"
    assert end.isoformat() == "2019-02-09"

    with pytest.raises(collector.CollectionError, match="later than"):
        collector.parse_date_range("2019-02-08", "2019-02-08")
    with pytest.raises(collector.CollectionError, match="YYYY-MM-DD"):
        collector.parse_date_range("20190208", "2019-02-09")


def test_image_job_from_row_accepts_optional_null_metadata():
    job = collector.image_job_from_row(["image-id", 1_700_000_000_000, None])

    assert job.index == "image-id"
    assert job.time_ms == 1_700_000_000_000
    assert job.orbit is None
    assert job.product_id is None


def test_normalize_dataframe_preserves_values_and_timezones():
    bands = (collector.PRIMARY_BAND,)
    frame = pd.DataFrame(
        {
            "longitude": [-74.005, -73.995, -73.985],
            "latitude": [4.595, 4.605, 4.615],
            collector.PRIMARY_BAND: [-1.25, 1850.5, None],
            collector.validity_column(0): [1, 1, 0],
            "geo": [None, None, None],
        }
    )

    result = collector.normalize_dataframe(frame, make_job(), bands)

    assert list(result.columns) == collector.output_columns(bands)
    assert len(result) == 2
    assert result[collector.PRIMARY_BAND].tolist() == [-1.25, 1850.5]
    assert str(result["date"].dtype) == "datetime64[ns, UTC]"
    assert str(result["date_colombia"].dtype) == "datetime64[ns, America/Bogota]"
    assert result.loc[0, "date"].utcoffset() == timedelta(0)
    assert result.loc[0, "date_colombia"].utcoffset() == timedelta(hours=-5)
    assert result["orbit"].dtype == "Int64"


def test_normalize_dataframe_handles_empty_images():
    bands = (collector.PRIMARY_BAND,)

    result = collector.normalize_dataframe(pd.DataFrame(), make_job(), bands)

    assert result.empty
    assert list(result.columns) == collector.output_columns(bands)
    assert result[collector.PRIMARY_BAND].dtype == "float64"


def test_normalize_dataframe_preserves_ch4_when_auxiliary_band_is_masked():
    auxiliary_band = "aerosol_height"
    bands = (collector.PRIMARY_BAND, auxiliary_band)
    frame = pd.DataFrame(
        {
            "longitude": [-74.005, -73.995],
            "latitude": [4.595, 4.605],
            collector.PRIMARY_BAND: [1850.5, 1851.5],
            auxiliary_band: [100.0, 0.0],
            collector.validity_column(0): [1, 1],
            collector.validity_column(1): [1, 0],
        }
    )

    result = collector.normalize_dataframe(frame, make_job(), bands)

    assert len(result) == 2
    assert result[collector.PRIMARY_BAND].tolist() == [1850.5, 1851.5]
    assert result[auxiliary_band].iloc[0] == 100.0
    assert pd.isna(result[auxiliary_band].iloc[1])

    with pytest.raises(collector.CollectionError, match="missing sampled columns"):
        collector.normalize_dataframe(
            frame.drop(columns=collector.validity_column(1)), make_job(), bands
        )


def test_output_path_is_partitioned_and_stable(tmp_path):
    job = make_job(index="image/with unsafe:value")

    first = collector.output_path_for_job(tmp_path, job)
    second = collector.output_path_for_job(tmp_path, job)

    assert first == second
    assert first.parent.parent.name == "year=2019"
    assert first.parent.name == "month=02"
    assert "/" not in first.name
    assert first.suffix == ".parquet"


def test_prepare_output_rejects_incompatible_configuration(tmp_path):
    output = tmp_path / "dataset"
    config = collector.collection_config((collector.PRIMARY_BAND,), nominal_only=False)

    collector.prepare_output_directory(output, config)
    collector.prepare_output_directory(output, config)

    incompatible = collector.collection_config(
        (collector.PRIMARY_BAND,), nominal_only=True
    )
    with pytest.raises(collector.CollectionError, match="different collection configuration"):
        collector.prepare_output_directory(output, incompatible)

    assert config["grid"] == "native-primary-band-projection"
    assert config["mask_policy"] == "primary-band-valid-with-nullable-auxiliary-bands"


def test_atomic_parquet_can_be_validated_for_resume(tmp_path):
    bands = (collector.PRIMARY_BAND,)
    job = make_job()
    raw = pd.DataFrame(
        {
            "longitude": [-74.005],
            "latitude": [4.595],
            collector.PRIMARY_BAND: [1850.5],
            collector.validity_column(0): [1],
        }
    )
    normalized = collector.normalize_dataframe(raw, job, bands)
    destination = collector.output_path_for_job(tmp_path, job)

    collector.prepare_output_directory(
        tmp_path, collector.collection_config(bands, nominal_only=False)
    )
    collector.write_parquet_atomic(normalized, destination)

    assert destination.is_file()
    schema = collector.expected_parquet_schema(bands)
    assert collector.existing_parquet_rows(destination, schema) == 1
    assert not list(destination.parent.glob("*.tmp"))
    assert len(pd.read_parquet(tmp_path)) == 1

    wrong_schema_path = destination.with_name("wrong-schema.parquet")
    normalized.astype({"longitude": "string"}).to_parquet(wrong_schema_path, index=False)
    assert collector.existing_parquet_rows(wrong_schema_path, schema) is None


def test_retryable_error_recognizes_transient_http_status():
    error = RuntimeError("service unavailable")
    error.resp = SimpleNamespace(status=503)

    assert collector.is_retryable_error(error)
    assert collector.is_retryable_error(TimeoutError("timed out"))
    assert collector.is_retryable_error(RuntimeError("Quota exceeded."))
    assert collector.is_retryable_error(RuntimeError("Service Unavailable"))
    assert not collector.is_retryable_error(ValueError("band does not exist"))


def test_collect_image_retries_then_writes(monkeypatch, tmp_path):
    bands = (collector.PRIMARY_BAND,)
    job = make_job()
    calls = 0

    def fake_fetch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary timeout")
        return pd.DataFrame(
            {
                    "longitude": [-74.005],
                    "latitude": [4.595],
                    collector.PRIMARY_BAND: [1850.5],
                    collector.validity_column(0): [1],
                }
        )

    monkeypatch.setattr(collector, "fetch_image_dataframe", fake_fetch)

    result = collector.collect_image(
        job=job,
        region=object(),
        bands=bands,
        output=tmp_path,
        page_size=100,
        tile_scale=1,
        max_attempts=3,
        sleep=lambda _: None,
    )

    assert calls == 3
    assert result.attempts == 3
    assert result.rows == 1
    assert result.path.is_file()


def test_collect_image_stops_before_next_request(monkeypatch, tmp_path):
    stop_event = Event()
    stop_event.set()
    monkeypatch.setattr(
        collector,
        "fetch_image_dataframe",
        lambda *args, **kwargs: pytest.fail("fetch should not start after interruption"),
    )

    with pytest.raises(collector.CollectionError, match="interrupted before fetching"):
        collector.collect_image(
            job=make_job(),
            region=object(),
            bands=(collector.PRIMARY_BAND,),
            output=tmp_path,
            page_size=100,
            tile_scale=1,
            max_attempts=1,
            stop_event=stop_event,
        )


def test_collect_image_writes_valid_empty_parquet(monkeypatch, tmp_path):
    bands = (collector.PRIMARY_BAND,)
    job = make_job()
    monkeypatch.setattr(collector, "fetch_image_dataframe", lambda *args, **kwargs: pd.DataFrame())

    result = collector.collect_image(
        job=job,
        region=object(),
        bands=bands,
        output=tmp_path,
        page_size=100,
        tile_scale=1,
        max_attempts=1,
    )

    assert result.rows == 0
    assert collector.existing_parquet_rows(
        result.path, collector.expected_parquet_schema(bands)
    ) == 0


def test_run_collection_does_not_submit_more_jobs_after_interrupt(monkeypatch, tmp_path):
    calls = []
    jobs = [make_job(index=f"image-{position}") for position in range(3)]

    def interrupt(job, *args, **kwargs):
        calls.append(job.index)
        raise KeyboardInterrupt

    monkeypatch.setattr(collector, "collect_image", interrupt)

    with pytest.raises(KeyboardInterrupt):
        collector.run_collection(
            jobs=jobs,
            region=object(),
            bands=(collector.PRIMARY_BAND,),
            output=tmp_path,
            workers=1,
            page_size=100,
            tile_scale=1,
            max_attempts=1,
            overwrite=False,
        )

    assert calls == ["image-0"]


def test_output_lock_rejects_concurrent_writer(tmp_path):
    with collector.lock_output_directory(tmp_path):
        with pytest.raises(collector.CollectionError, match="another collector"):
            with collector.lock_output_directory(tmp_path):
                pass
