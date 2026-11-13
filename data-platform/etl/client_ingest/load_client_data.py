import argparse
import csv
import json
import re
import uuid
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from sqlalchemy import text

import sys
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'etl' / 'src'))
from database import get_engine
SPEC = Path(__file__).with_name("spec.yaml")
IATA = {
    "Hyderabad": "HYD", "Bengaluru": "BLR", "Mumbai": "BOM",
    "New Delhi": "DEL", "Chennai": "MAA", "Kolkata": "CCU", "Pune": "PNQ"
}
ORDER = [
    "product_master", "warehouse_master", "supplier_master", "carriers",
    "sales_history", "inventory_snapshot", "supplier_lead_times",
    "supplier_incidents", "purchase_order_history", "shipment_history"
]


def validate(row, rules):
    errors = []
    for name, rule in rules.items():
        value = (row.get(name) or "").strip()
        if not value:
            if rule.get("required"):
                errors.append(f"{name}: required value is blank")
            continue

        kind = rule.get("type")
        fmt = str(rule.get("format", "")).lower()

        try:
            if kind == "date":
                datetime.strptime(value, "%Y-%m-%d")
            elif kind == "integer":
                number = int(value)
                if "positive" in fmt and number <= 0:
                    errors.append(f"{name}: must be positive")
                if "non-negative" in fmt and number < 0:
                    errors.append(f"{name}: must be non-negative")
            elif kind == "decimal":
                number = Decimal(value)
                if "0 to 1" in fmt and not 0 <= number <= 1:
                    errors.append(f"{name}: must be between 0 and 1")
                if "positive" in fmt and number <= 0:
                    errors.append(f"{name}: must be positive")
                if "2 decimal" in fmt and number.as_tuple().exponent < -2:
                    errors.append(f"{name}: maximum 2 decimal places")
            elif kind == "boolean" and value.lower() not in {
                "true", "false", "1", "0", "yes", "no"
            }:
                errors.append(f"{name}: must be true or false")
        except (ValueError, InvalidOperation):
            errors.append(f"{name}: invalid {kind} value")
            continue

        patterns = [
            ("prd-", r"PRD-\d{5}"), ("sup-", r"SUP-\d{4}"),
            ("po-", r"PO-\d{5}"), ("sh-", r"SH-\d{6}"),
            ("inc-", r"INC-\d{6}"), ("car-", r"CAR-\d{2}")
        ]
        for marker, pattern in patterns:
            if marker in fmt and not re.fullmatch(pattern, value, re.I):
                errors.append(f"{name}: invalid format")
                break

        if "email" in fmt and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            errors.append(f"{name}: invalid email")
        if "10 digits" in fmt and not re.fullmatch(r"\d{10}", value):
            errors.append(f"{name}: must contain 10 digits")
        if "6 digits" in fmt and not re.fullmatch(r"\d{6}", value):
            errors.append(f"{name}: must contain 6 digits")
        if "low/medium/high" in fmt and value.lower() not in {"low", "medium", "high"}:
            errors.append(f"{name}: invalid severity")
        if "delivered" in fmt and value.lower() not in {"delivered", "delayed", "in transit"}:
            errors.append(f"{name}: invalid shipment status")
        if "open" in fmt and "received" in fmt and value.lower() not in {"open", "received", "cancelled"}:
            errors.append(f"{name}: invalid PO status")

    return errors


def get_id(conn, entity, code, prefix, width=6, year=None, city_code=None):
    existing = conn.execute(text("""
        SELECT canonical_id FROM client_id_mapping
        WHERE entity_type=:entity AND client_code=:code
    """), {"entity": entity, "code": code}).scalar_one_or_none()
    if existing:
        return existing

    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": entity}
    )

    existing = conn.execute(text("""
        SELECT canonical_id FROM client_id_mapping
        WHERE entity_type=:entity AND client_code=:code
    """), {"entity": entity, "code": code}).scalar_one_or_none()
    if existing:
        return existing

    ids = conn.execute(text("""
        SELECT canonical_id FROM client_id_mapping WHERE entity_type=:entity
    """), {"entity": entity}).scalars().all()

    if city_code:
        matching = [x for x in ids if x.startswith(f"WH-{city_code}-")]
        nums = [int(x.rsplit("-", 1)[1]) for x in matching]
        canonical = f"WH-{city_code}-{max(nums, default=0)+1:02d}"
    elif year:
        matching = [x for x in ids if x.startswith(f"{prefix}-{year}-")]
        nums = [int(x.rsplit("-", 1)[1]) for x in matching]
        canonical = f"{prefix}-{year}-{max(nums, default=0)+1:06d}"
    else:
        nums = [int(x.rsplit("-", 1)[1]) for x in ids
                if x.rsplit("-", 1)[-1].isdigit()]
        canonical = f"{prefix}-{max(nums, default=0)+1:0{width}d}"

    conn.execute(text("""
        INSERT INTO client_id_mapping(entity_type, client_code, canonical_id)
        VALUES (:entity, :code, :canonical)
    """), {"entity": entity, "code": code, "canonical": canonical})
    return canonical


def add_ids(conn, key, row, warehouse_cities):
    mappings = [
        ("product_code", "product", "SKU", "sku_id", 6),
        ("supplier_code", "supplier", "SUP", "supplier_id", 5),
    ]
    for source, entity, prefix, target, width in mappings:
        if row.get(source):
            row[target] = get_id(conn, entity, row[source], prefix, width)

    if key == "purchase_order_history":
        year = datetime.strptime(row["order_date"], "%Y-%m-%d").year
        row["po_id"] = get_id(
            conn, "purchase_order", row["po_number"], "PO", year=year
        )

    if key == "shipment_history":
        year = datetime.strptime(row["dispatch_date"], "%Y-%m-%d").year
        row["shipment_id"] = get_id(
            conn, "shipment", row["shipment_id"], "SHP", year=year
        )
        row["client_shipment_id"] = row["shipment_id"]
        row["po_id"] = get_id(
            conn, "purchase_order", row["po_number"], "PO",
            year=datetime.strptime(row["dispatch_date"], "%Y-%m-%d").year
        )

    warehouse_field = (
        "destination_warehouse_code" if key == "shipment_history"
        else "warehouse_code"
    )
    if row.get(warehouse_field):
        city = warehouse_cities.get(row[warehouse_field])
        if not city or city not in IATA:
            raise ValueError(f"Cannot map warehouse city for {row[warehouse_field]}")
        row["warehouse_id"] = get_id(
            conn, "warehouse", row[warehouse_field], "WH",
            city_code=IATA[city]
        )

    return row


def make_record_key(key, row):
    fields = {
        "product_master": ["product_code"],
        "warehouse_master": ["warehouse_code"],
        "supplier_master": ["supplier_code"],
        "carriers": ["carrier_code"],
        "sales_history": ["sale_date", "order_number", "product_code", "warehouse_code"],
        "inventory_snapshot": ["snapshot_date", "product_code", "warehouse_code"],
        "supplier_lead_times": ["supplier_code", "product_code", "effective_date"],
        "supplier_incidents": ["incident_id"],
        "purchase_order_history": ["po_number"],
        "shipment_history": ["shipment_id"],
    }[key]
    return "|".join(str(row.get(field, "")) for field in fields)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    args = parser.parse_args()

    folder = Path(args.dir)
    if not folder.is_dir():
        parser.error(f"Folder not found: {folder}")

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    paths = {p.stem: p for p in folder.glob("*.csv")}
    engine = get_engine()
    run_id = str(uuid.uuid4())

    warehouse_cities = {}
    if "warehouse_master" in paths:
        with paths["warehouse_master"].open(
            newline="", encoding="utf-8-sig"
        ) as f:
            for row in csv.DictReader(f):
                warehouse_cities[row["warehouse_code"].strip()] = row["city"].strip()

    print(f"Run ID: {run_id}")
    totals = Counter()

    for key in ORDER:
        path = paths.get(key)
        if not path:
            continue

        rules = spec["files"][key]["columns"]
        counts = Counter()
        reasons = Counter()

        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            missing = set(rules) - set(reader.fieldnames or [])
            if missing:
                print(f"{path.name}: missing columns {sorted(missing)}")
                continue

            for row_number, raw in enumerate(reader, start=2):
                counts["read"] += 1
                row = {k: (v.strip() if v else "") for k, v in raw.items()}
                errors = validate(row, rules)

                if key == "shipment_history" and "carriers" in paths:
                    with paths["carriers"].open(
                        newline="", encoding="utf-8-sig"
                    ) as cf:
                        carrier_names = {
                            x["carrier_name"].strip().casefold()
                            for x in csv.DictReader(cf)
                        }
                    if row.get("carrier_name", "").casefold() not in carrier_names:
                        errors.append("carrier_name: not found in carriers.csv")

                if errors:
                    reason = "; ".join(errors)
                    reasons[reason] += 1
                    counts["rejected"] += 1
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO client_ingest_rejects
                            (run_id, entity_type, source_file, source_row,
                             raw_record, rejection_reason)
                            VALUES (:run, :entity, :file, :row,
                                    CAST(:raw AS jsonb), :reason)
                        """), {
                            "run": run_id, "entity": key, "file": path.name,
                            "row": row_number, "raw": json.dumps(raw),
                            "reason": reason
                        })
                    continue

                try:
                    with engine.begin() as conn:
                        row = add_ids(conn, key, row, warehouse_cities)
                        conn.execute(text("""
                            INSERT INTO client_ingest_staging
                            (entity_type, record_key, source_file, source_row,
                             canonical_record)
                            VALUES (:entity, :key, :file, :row, CAST(:record AS jsonb))
                            ON CONFLICT (entity_type, record_key) DO UPDATE SET
                              source_file=EXCLUDED.source_file,
                              source_row=EXCLUDED.source_row,
                              canonical_record=EXCLUDED.canonical_record,
                              loaded_at=NOW()
                        """), {
                            "entity": key, "key": make_record_key(key, row),
                            "file": path.name, "row": row_number,
                            "record": json.dumps(row)
                        })
                    counts["loaded"] += 1
                except Exception as exc:
                    reason = f"load error: {exc}"
                    reasons[reason] += 1
                    counts["rejected"] += 1
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO client_ingest_rejects
                            (run_id, entity_type, source_file, source_row,
                             raw_record, rejection_reason)
                            VALUES (:run, :entity, :file, :row,
                                    CAST(:raw AS jsonb), :reason)
                        """), {
                            "run": run_id, "entity": key, "file": path.name,
                            "row": row_number, "raw": json.dumps(raw),
                            "reason": reason[:4000]
                        })

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO client_ingest_reports
                (run_id, source_file, entity_type, rows_read, rows_loaded,
                 rows_rejected, top_rejection_reasons)
                VALUES (:run, :file, :entity, :read, :loaded, :rejected,
                        CAST(:reasons AS jsonb))
            """), {
                "run": run_id, "file": path.name, "entity": key,
                "read": counts["read"], "loaded": counts["loaded"],
                "rejected": counts["rejected"],
                "reasons": json.dumps(dict(reasons.most_common(5)))
            })

        totals.update(counts)
        print(
            f"{path.name}: read={counts['read']} "
            f"loaded={counts['loaded']} rejected={counts['rejected']}"
        )
        for reason, count in reasons.most_common(3):
            print(f"  {count}x {reason}")

    print(
        f"TOTAL: read={totals['read']} loaded={totals['loaded']} "
        f"rejected={totals['rejected']}"
    )
    print(f"Report run ID: {run_id}")


if __name__ == "__main__":
    main()


