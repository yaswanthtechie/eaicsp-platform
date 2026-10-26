"""
Sensor config generated from the shared seed warehouses.

Reads the seed warehouse CSV (data-platform/out/ if generated, else
data-platform/seed/samples/), keeps canonical ids (WH-XXX-NN), creates
SENSORS_PER_WAREHOUSE sensors per warehouse and writes config/sensors.json.
Nothing is hardcoded: re-run after the seed changes.

Run (from ml-services/anomaly-detection):
    python -m src.sensor_config
    python -m src.sensor_config --csv <file> --column <id column>
"""

import argparse
import csv
import json
import os
import re
from pathlib import Path


WAREHOUSE_PATTERN = re.compile(r"WH-[A-Z]{3}-[0-9]{2}")
SENSOR_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")
ID_COLUMNS = ("warehouse_id", "warehouse_code", "id")
SENSORS_PER_WAREHOUSE = 2

project_root = Path(__file__).resolve().parent.parent
repo_root = project_root.parent.parent
CONFIG_PATH = project_root / "config" / "sensors.json"


def find_warehouse_csv(explicit=None):

    if explicit:
        path = Path(explicit)

        if not path.is_file():
            raise FileNotFoundError(f"Warehouse CSV not found: {path}")

        return path

    env = os.environ.get("SEED_WAREHOUSES_CSV")

    if env:
        return find_warehouse_csv(env)

    seed_root = repo_root / "data-platform"

    for pattern in ("out/*warehouse*.csv", "seed/samples/*warehouse*.csv"):
        matches = sorted(seed_root.glob(pattern))

        if matches:
            return matches[0]

    raise FileNotFoundError(
        "No seed warehouse CSV found under data-platform/. Generate the seed "
        "(from data-platform/: python -m seed.generate --out out/) or pass --csv."
    )


def read_warehouse_ids(path, column=None):

    with open(path, newline="", encoding="utf-8-sig") as handle:

        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []

        name = column or next((c for c in ID_COLUMNS if c in fields), None)

        if name is None or name not in fields:
            raise ValueError(
                f"No warehouse id column in {path}. Columns: {fields}. "
                "Use --column."
            )

        ids = []

        for row in reader:
            value = (row[name] or "").strip()

            if WAREHOUSE_PATTERN.fullmatch(value) and value not in ids:
                ids.append(value)

    if not ids:
        raise ValueError(f"No canonical warehouse ids (WH-XXX-NN) in {path}.")

    return sorted(ids)


def generate_sensors(warehouse_ids, per_warehouse=SENSORS_PER_WAREHOUSE):

    if per_warehouse < 1:
        raise ValueError("per_warehouse must be at least 1.")

    return [
        {"sensor_id": f"{wh}-S{i}", "warehouse_id": wh}
        for wh in warehouse_ids
        for i in range(1, per_warehouse + 1)
    ]


def write_config(sensors, source_name, path=CONFIG_PATH):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"source": source_name, "sensors": sensors}, handle, indent=2)
        handle.write("\n")

    return path


def load_sensors(path=CONFIG_PATH):

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Generate it: python -m src.sensor_config"
        )

    with open(path, encoding="utf-8") as handle:
        sensors = json.load(handle)["sensors"]

    seen = set()

    for sensor in sensors:

        sid, wh = sensor["sensor_id"], sensor["warehouse_id"]

        if not SENSOR_ID_PATTERN.fullmatch(sid):
            raise ValueError(f"Bad sensor_id in config: {sid!r}")

        if not WAREHOUSE_PATTERN.fullmatch(wh):
            raise ValueError(f"Bad warehouse_id in config: {wh!r}")

        if sid in seen:
            raise ValueError(f"Duplicate sensor_id in config: {sid}")

        seen.add(sid)

    if not sensors:
        raise ValueError("Sensor config is empty.")

    return sensors


def sensor_map(sensors):
    """sensor_id -> warehouse_id."""

    return {s["sensor_id"]: s["warehouse_id"] for s in sensors}


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--column", default=None)
    parser.add_argument("--per-warehouse", type=int, default=SENSORS_PER_WAREHOUSE)
    parser.add_argument("--out", default=str(CONFIG_PATH))
    args = parser.parse_args(argv)

    source = find_warehouse_csv(args.csv)
    warehouses = read_warehouse_ids(source, args.column)
    sensors = generate_sensors(warehouses, args.per_warehouse)
    out = write_config(sensors, source.name, args.out)

    print(f"source: {source}")
    print(f"warehouses: {warehouses}")
    print(f"sensors: {len(sensors)} -> {out}")


if __name__ == "__main__":
    main()