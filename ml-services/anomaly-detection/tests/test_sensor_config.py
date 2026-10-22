import pytest

from src.sensor_config import (
    CONFIG_PATH,
    SENSORS_PER_WAREHOUSE,
    find_warehouse_csv,
    generate_sensors,
    load_sensors,
    read_warehouse_ids,
    sensor_map,
    write_config,
)

SIX = {
    "WH-BLR-01",
    "WH-BOM-01",
    "WH-CCU-01",
    "WH-DEL-01",
    "WH-HYD-01",
    "WH-MAA-01",
}


def _csv(tmp_path, text):
    path = tmp_path / "warehouses.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_canonical_ids_only_and_dedupes(tmp_path):

    path = _csv(
        tmp_path,
        "warehouse_id,city\nWH-BOM-01,Mumbai\nWH-BLR-01,Bengaluru\nWH1,x\nWH-BLR-01,dup\n",
    )

    assert read_warehouse_ids(path) == ["WH-BLR-01", "WH-BOM-01"]


def test_missing_id_column_raises(tmp_path):

    with pytest.raises(ValueError):
        read_warehouse_ids(_csv(tmp_path, "name,city\na,b\n"))


def test_no_canonical_ids_raises(tmp_path):

    with pytest.raises(ValueError):
        read_warehouse_ids(_csv(tmp_path, "warehouse_id\nWH1\n"))


def test_custom_column(tmp_path):

    path = _csv(tmp_path, "code\nWH-DEL-01\n")

    assert read_warehouse_ids(path, column="code") == ["WH-DEL-01"]


def test_generate_sensors_and_map():

    sensors = generate_sensors(["WH-BLR-01", "WH-DEL-01"], 3)

    assert len(sensors) == 6
    assert sensors[0] == {"sensor_id": "WH-BLR-01-S1", "warehouse_id": "WH-BLR-01"}
    assert sensor_map(sensors)["WH-DEL-01-S3"] == "WH-DEL-01"

    with pytest.raises(ValueError):
        generate_sensors(["WH-BLR-01"], 0)


def test_write_and_load_round_trip(tmp_path):

    sensors = generate_sensors(["WH-BLR-01"], 2)
    path = write_config(sensors, "warehouses.csv", tmp_path / "s.json")

    assert load_sensors(path) == sensors


def test_load_rejects_bad_config(tmp_path):

    bad = [{"sensor_id": "a b", "warehouse_id": "WH-BLR-01"}]
    path = write_config(bad, "x", tmp_path / "bad.json")

    with pytest.raises(ValueError):
        load_sensors(path)

    with pytest.raises(FileNotFoundError):
        load_sensors(tmp_path / "missing.json")


def test_find_csv_explicit_path_must_exist(tmp_path):

    with pytest.raises(FileNotFoundError):
        find_warehouse_csv(tmp_path / "nope.csv")


def test_committed_config_covers_the_six_seed_warehouses():

    sensors = load_sensors(CONFIG_PATH)

    assert {s["warehouse_id"] for s in sensors} == SIX
    assert len(sensors) == len(SIX) * SENSORS_PER_WAREHOUSE