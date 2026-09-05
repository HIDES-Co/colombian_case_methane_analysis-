import json

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import Affine

from common import covariables as malla
from data_collection import collect_covariates_gee as cov
from data_collection.collect_gee_colombia import CollectionError


def escribir_tif(path, datos, lon_oeste, lat_norte, paso):
    transform = Affine(paso, 0.0, lon_oeste, 0.0, -paso, lat_norte)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=datos.shape[0],
        width=datos.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(datos.astype("float32"), 1)


def malla_de_prueba(paso=0.01, etiqueta="0p01", lon_oeste=-72.0, lat_norte=12.0, ancho=4, alto=4):
    return cov.MallaRaster(
        etiqueta=etiqueta,
        paso=paso,
        lon_oeste=lon_oeste,
        lat_norte=lat_norte,
        ancho=ancho,
        alto=alto,
    )


def centros(malla_raster):
    lons, lats = [], []
    for fila in range(malla_raster.alto):
        for col in range(malla_raster.ancho):
            lons.append(malla_raster.lon_oeste + (col + 0.5) * malla_raster.paso)
            lats.append(malla_raster.lat_norte - (fila + 0.5) * malla_raster.paso)
    return pd.DataFrame({"longitude": np.round(lons, 5), "latitude": np.round(lats, 5)})


def test_malla_para_bbox_se_ajusta_hacia_afuera_y_queda_alineada():
    bbox = (-81.837, -4.229, -66.847, 13.586)
    resultado = cov.malla_para_bbox(bbox, 0.01, "0p01")
    assert resultado.lon_oeste <= bbox[0]
    assert resultado.lat_norte >= bbox[3]
    assert resultado.lon_oeste + resultado.ancho * 0.01 >= bbox[2]
    assert resultado.lat_norte - resultado.alto * 0.01 <= bbox[1]
    desfase_lon = (resultado.lon_oeste - malla.ORIGEN_LON) / 0.01
    desfase_lat = (malla.ORIGEN_LAT - resultado.lat_norte) / 0.01
    assert abs(desfase_lon - round(desfase_lon)) < 1e-6
    assert abs(desfase_lat - round(desfase_lat)) < 1e-6


def test_indices_malla_recupera_el_centro_del_pixel():
    filas, columnas = malla.indices_malla([-71.495], [11.925], malla.PASO_0P01)
    centro_lon = malla.ORIGEN_LON + (columnas[0] + 0.5) * malla.PASO_0P01
    centro_lat = malla.ORIGEN_LAT - (filas[0] + 0.5) * malla.PASO_0P01
    assert centro_lon == pytest.approx(-71.495)
    assert centro_lat == pytest.approx(11.925)


def test_celda_0p06_contiene_36_pixeles_de_0p01():
    # La celda 0.06° (fila 633, col 800) cubre lon (-72.00, -71.94] y lat (11.96, 12.02]:
    # las fronteras son -120 + k*0.06 y 50 - k*0.06, no números "redondos".
    lons = [-71.995 + 0.01 * i for i in range(6)]
    lats = [11.965 + 0.01 * i for i in range(6)]
    rejilla = [(lon, lat) for lon in lons for lat in lats]
    ids = malla.celda_0p06_id([p[0] for p in rejilla], [p[1] for p in rejilla])
    assert len(set(ids.tolist())) == 1
    vecino_lon = malla.celda_0p06_id([-71.935], [11.965])
    vecino_lat = malla.celda_0p06_id([-71.995], [11.955])
    assert vecino_lon[0] != ids[0]
    assert vecino_lat[0] != ids[0]


def test_rango_meses_es_semiabierto_y_cruza_el_anio():
    assert cov.rango_meses("2021-12", "2022-02") == [(2021, 12), (2022, 1)]
    with pytest.raises(CollectionError):
        cov.rango_meses("2022-1", "2022-02")
    with pytest.raises(CollectionError):
        cov.rango_meses("2022-02", "2022-02")


def test_listado_de_jobs_dem_y_albedo():
    mallas = {"0p01": malla_de_prueba(), "0p06": malla_de_prueba(paso=0.06, etiqueta="0p06")}
    dem = cov.jobs_dem(mallas)
    assert len(dem) == 6
    assert len({job.stem for job in dem}) == 6
    albedo = cov.jobs_albedo(mallas, [(2022, 1), (2022, 2)], [2022], qa_max=0)
    assert len(albedo) == 2 * 3 * 2 + 1 * 3 * 2
    enero = next(job for job in albedo if job.stem == "albedo_bsa_0p01_2022-01")
    assert enero.params == ("bsa", "2022-01-01", "2022-02-01", 0)
    assert enero.subdir == "mensual"
    anual = next(job for job in albedo if job.stem == "albedo_bsa_0p01_2022")
    assert anual.params == ("bsa", "2022-01-01", "2023-01-01", 0)
    assert anual.subdir == "anual"


def test_raster_valido_detecta_rejilla_y_corrupcion(tmp_path):
    rejilla = malla_de_prueba()
    ruta = tmp_path / "capa.tif"
    escribir_tif(ruta, np.zeros((4, 4)), rejilla.lon_oeste, rejilla.lat_norte, rejilla.paso)
    assert cov.raster_valido(ruta, rejilla)
    otra = malla_de_prueba(ancho=5)
    assert not cov.raster_valido(ruta, otra)
    corrupto = tmp_path / "corrupto.tif"
    corrupto.write_bytes(b"no soy un geotiff")
    assert not cov.raster_valido(corrupto, rejilla)
    assert not cov.raster_valido(tmp_path / "no_existe.tif", rejilla)


def test_muestrear_en_devuelve_valores_y_nan(tmp_path):
    rejilla = malla_de_prueba()
    datos = np.arange(16, dtype="float64").reshape(4, 4)
    datos[1, 1] = cov.NODATA_SENTINEL
    ruta = tmp_path / "capa.tif"
    escribir_tif(ruta, datos, rejilla.lon_oeste, rejilla.lat_norte, rejilla.paso)
    lon = np.array([-71.995, -71.965, -71.985, -60.0])
    lat = np.array([11.995, 11.965, 11.985, 11.995])
    valores = cov.muestrear_en(ruta, lon, lat)
    assert valores[0] == 0.0
    assert valores[1] == 15.0
    assert np.isnan(valores[2])  # centinela nodata
    assert np.isnan(valores[3])  # fuera del ráster


def _rasters_dem(tmp_path, rejilla, oceano=()):
    datos_0p01 = np.arange(16, dtype="float64").reshape(4, 4) * 100.0
    for fila, col in oceano:
        datos_0p01[fila, col] = cov.NODATA_SENTINEL
    escribir_tif(
        tmp_path / "glo30_mean_0p01.tif", datos_0p01, rejilla.lon_oeste, rejilla.lat_norte, 0.01
    )
    escribir_tif(
        tmp_path / "glo30_stdDev_0p01.tif",
        np.full((4, 4), 5.0),
        rejilla.lon_oeste,
        rejilla.lat_norte,
        0.01,
    )
    for nombre, valor in (("stdDev", 7.0), ("min", 1.0), ("max", 900.0)):
        escribir_tif(
            tmp_path / f"glo30_{nombre}_0p06.tif",
            np.full((1, 1), valor),
            rejilla.lon_oeste,
            rejilla.lat_norte,
            0.06,
        )


def test_construir_estaticas_dem_escribe_columnas_y_rellena_oceano(tmp_path):
    rejilla = malla_de_prueba()
    _rasters_dem(tmp_path, rejilla, oceano=[(0, 0)])
    malla_df = centros(rejilla)
    covariables_dir = tmp_path / "cov"
    cov.construir_estaticas_dem(tmp_path, covariables_dir, malla_df)
    tabla = pd.read_parquet(covariables_dir / "estaticas_0p01.parquet")
    assert len(tabla) == 16
    esperadas = {
        "elev_m",
        "elev_std_1km",
        "elev_std_7km",
        "elev_min_7km",
        "elev_max_7km",
        "elev_res_nativa_m",
        "celda_0p06_id",
    }
    assert esperadas.issubset(tabla.columns)
    assert not tabla[list(esperadas)].isna().any().any()
    fila_oceano = tabla.query("longitude == -71.995 and latitude == 11.995")
    assert fila_oceano["elev_m"].iloc[0] == 0.0
    fila_tierra = tabla.query("longitude == -71.965 and latitude == 11.995")
    assert fila_tierra["elev_m"].iloc[0] == 300.0
    assert fila_tierra["elev_std_7km"].iloc[0] == 7.0
    hermano = json.loads((covariables_dir / "estaticas_0p01.json").read_text())
    assert hermano["variables"]["dem_glo30"]["relleno_oceano_0m"]["elev_m"] == 1
    assert tabla["celda_0p06_id"].nunique() == 1


def test_construir_estaticas_dem_falla_con_demasiado_sin_dato(tmp_path):
    rejilla = malla_de_prueba()
    oceano = [(f, c) for f in range(4) for c in range(2)]  # 50 % sin dato
    _rasters_dem(tmp_path, rejilla, oceano=oceano)
    with pytest.raises(CollectionError, match="sin dato GLO30"):
        cov.construir_estaticas_dem(tmp_path, tmp_path / "cov", centros(rejilla))


def test_construir_estaticas_dem_exige_los_geotiff(tmp_path):
    with pytest.raises(CollectionError, match="faltan GeoTIFF"):
        cov.construir_estaticas_dem(tmp_path, tmp_path / "cov", centros(malla_de_prueba()))


def test_actualizar_estaticas_agrega_columnas_sin_tocar_las_previas(tmp_path):
    malla_df = centros(malla_de_prueba(ancho=2, alto=1))
    primera = pd.DataFrame({"a": [1.0, 2.0]})
    cov.actualizar_estaticas(tmp_path, malla_df, primera, "grupo_a", {"fuente": "x"})
    segunda = pd.DataFrame({"b": [3.0, 4.0]})
    cov.actualizar_estaticas(tmp_path, malla_df, segunda, "grupo_b", {"fuente": "y"})
    tabla = pd.read_parquet(tmp_path / "estaticas_0p01.parquet")
    assert sorted(tabla.columns) == ["a", "b", "latitude", "longitude"]
    assert tabla["a"].tolist() == [1.0, 2.0]
    reemplazo = pd.DataFrame({"a": [9.0, 9.0]})
    cov.actualizar_estaticas(tmp_path, malla_df, reemplazo, "grupo_a", {"fuente": "z"})
    tabla = pd.read_parquet(tmp_path / "estaticas_0p01.parquet")
    assert tabla["a"].tolist() == [9.0, 9.0]
    assert tabla["b"].tolist() == [3.0, 4.0]
    hermano = json.loads((tmp_path / "estaticas_0p01.json").read_text())
    assert set(hermano["variables"]) == {"grupo_a", "grupo_b"}
    assert hermano["variables"]["grupo_a"]["fuente"] == "z"


def test_construir_mensuales_albedo_descarta_oceano_y_normaliza_nobs(tmp_path):
    rejilla = malla_de_prueba(ancho=2, alto=1)
    mensual = tmp_path / "mensual"
    mensual.mkdir()
    for periodo, base in (("2022-01", 0.10), ("2022-02", 0.20)):
        bsa = np.array([[base, cov.NODATA_SENTINEL]])
        wsa = np.array([[base + 0.01, cov.NODATA_SENTINEL]])
        nobs = np.array([[4.0, cov.NODATA_SENTINEL]])
        for tipo, datos in (("bsa", bsa), ("wsa", wsa), ("nobs", nobs)):
            escribir_tif(
                mensual / f"albedo_{tipo}_0p01_{periodo}.tif",
                datos,
                rejilla.lon_oeste,
                rejilla.lat_norte,
                0.01,
            )
    covariables_dir = tmp_path / "cov"
    cov.construir_mensuales_albedo(tmp_path, covariables_dir, centros(rejilla), qa_max=0)
    tabla = pd.read_parquet(covariables_dir / "mensuales" / "albedo_swir_0p01.parquet")
    assert len(tabla) == 2  # el píxel océanico se descarta en ambos meses
    assert sorted(tabla["month"].tolist()) == [1, 2]
    assert tabla["albedo_swir"].tolist() == pytest.approx([0.10, 0.20])
    assert (tabla["albedo_swir_n_obs"] == 4.0).all()
    hermano = json.loads(
        (covariables_dir / "mensuales" / "albedo_swir_0p01.json").read_text()
    )
    assert hermano["meses"] == ["2022-01", "2022-02"]


def test_construir_estaticas_albedo_usa_los_anios_en_disco(tmp_path):
    rejilla = malla_de_prueba(ancho=2, alto=1)
    anual = tmp_path / "anual"
    anual.mkdir()
    for tipo, valor in (("bsa", 0.15), ("wsa", 0.18)):
        escribir_tif(
            anual / f"albedo_{tipo}_0p01_2022.tif",
            np.array([[valor, valor]]),
            rejilla.lon_oeste,
            rejilla.lat_norte,
            0.01,
        )
    covariables_dir = tmp_path / "cov"
    cov.construir_estaticas_albedo(tmp_path, covariables_dir, centros(rejilla), qa_max=0)
    tabla = pd.read_parquet(covariables_dir / "estaticas_0p01.parquet")
    assert tabla["albedo_swir_2022"].tolist() == pytest.approx([0.15, 0.15])
    assert tabla["albedo_swir_wsa_2022"].tolist() == pytest.approx([0.18, 0.18])
    assert (tabla["albedo_swir_res_nativa_m"] == 500).all()


def test_cargar_malla_ch4_deduplica_y_cachea(tmp_path):
    csv = tmp_path / "ch4.csv"
    csv.write_text(
        "longitude,latitude,otra\n"
        "-71.495,11.925,1\n"
        "-71.495,11.925000000000001,2\n"
        "-71.745,11.915,3\n"
    )
    malla_df = cov.cargar_malla_ch4(tmp_path, csv)
    assert len(malla_df) == 2
    assert (tmp_path / "malla_ch4_0p01.parquet").is_file()
    csv.unlink()  # la segunda lectura debe salir del caché
    otra_vez = cov.cargar_malla_ch4(tmp_path, csv)
    pd.testing.assert_frame_equal(malla_df, otra_vez)


def test_unir_covariables_estaticas_y_mensuales(tmp_path):
    malla_df = centros(malla_de_prueba(ancho=2, alto=1))
    estaticas = malla_df.assign(elev_m=[100.0, 200.0])
    estaticas.to_parquet(tmp_path / "estaticas_0p01.parquet", index=False)
    mensuales_dir = tmp_path / "mensuales"
    mensuales_dir.mkdir()
    mensual = malla_df.assign(year=2022, month=1, albedo_swir=[0.1, 0.2])
    mensual.to_parquet(mensuales_dir / "albedo_swir_0p01.parquet", index=False)

    df = malla_df.assign(year=[2022, 2022], month=[1, 2])
    unido = malla.unir_covariables(df, ["elev_m", "albedo_swir_mensual"], ruta=tmp_path)
    assert unido["elev_m"].tolist() == [100.0, 200.0]
    assert unido["albedo_swir"].iloc[0] == pytest.approx(0.1)
    assert np.isnan(unido["albedo_swir"].iloc[1])  # mes sin dato: cobertura parcial

    fantasma = pd.DataFrame(
        {"longitude": [-60.005], "latitude": [1.005], "year": [2022], "month": [1]}
    )
    con_pixel_fantasma = pd.concat([df, fantasma])
    with pytest.raises(ValueError, match="sin píxel"):
        malla.unir_covariables(con_pixel_fantasma, ["elev_m"], ruta=tmp_path)
    with pytest.raises(KeyError, match="no están"):
        malla.unir_covariables(df, ["no_existe"], ruta=tmp_path)
    sin_mes = malla_df.assign(year=1999, month=6)
    with pytest.raises(ValueError, match="ninguna fila"):
        malla.unir_covariables(sin_mes, ["albedo_swir_mensual"], ruta=tmp_path)


def test_configuracion_capa_distingue_capas():
    dem = cov.configuracion_capa("dem", qa_max=0)
    albedo = cov.configuracion_capa("albedo_swir", qa_max=1)
    assert dem["dataset"] == "COPERNICUS/DEM/GLO30"
    assert albedo["qa_max"] == 1
    assert dem["malla"]["origen_lon"] == malla.ORIGEN_LON
    with pytest.raises(CollectionError):
        cov.configuracion_capa("nubes", qa_max=0)
