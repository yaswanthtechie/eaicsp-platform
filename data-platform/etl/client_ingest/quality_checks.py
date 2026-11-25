"""Quality checks for a client ingestion run."""
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import text

DATE_COLUMNS = {
    "sales_history": ["sale_date"],
    "inventory_snapshot": ["snapshot_date"],
    "supplier_lead_times": ["effective_date"],
    "supplier_incidents": ["incident_date"],
    "shipment_history": ["dispatch_date", "planned_delivery_date", "actual_delivery_date"],
    "purchase_order_history": ["order_date", "expected_date", "received_date"],
}

REFERENCE_FILES = {
    "product_code": ("product_master", "product_code"),
    "warehouse_code": ("warehouse_master", "warehouse_code"),
    "supplier_code": ("supplier_master", "supplier_code"),
}

CHECK_FILES = {
    "sales_history": ["product_code", "warehouse_code"],
    "inventory_snapshot": ["product_code", "warehouse_code"],
    "purchase_order_history": ["product_code", "warehouse_code", "supplier_code"],
}


def _rows(folder, name):
    path = Path(folder) / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Required client file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _valid_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def evaluate_quality(folder, thresholds, rejected_rows=None):
    folder = Path(folder)
    result = {"freshness": {}, "referential_integrity": {}, "sales_gaps": {}}
    reasons = []
    today = date.today()
    rejected_rows = rejected_rows or set()

    def accepted_rows(name):
        rows = _rows(folder, name)
        filename = f"{name}.csv"
        return [
            row for index, row in enumerate(rows, start=2)
            if (filename, index) not in rejected_rows
            and (name, index) not in rejected_rows
        ]

    # Freshness: latest valid date in each dated source file.
    freshness_config = thresholds["freshness"]
    max_age = int(freshness_config["max_age_days"])
    per_file_age = freshness_config.get("per_file_max_age_days", {})
    for name, columns in DATE_COLUMNS.items():
        rows = accepted_rows(name)
        file_max_age = int(per_file_age.get(name, max_age))
        dates = [
            parsed
            for row in rows
            for column in columns
            if (parsed := _valid_date(row.get(column)))
        ]
        latest = max(dates) if dates else None
        age = (today - latest).days if latest else None
        passed = latest is not None and age <= file_max_age
        result["freshness"][name] = {
            "latest_date": latest.isoformat() if latest else None,
            "age_days": age,
            "max_age_days": file_max_age,
            "passed": passed,
        }
        if not passed:
            reasons.append(
                f"{name} freshness failed (latest={latest}, age_days={age}, limit={file_max_age})"
            )

    # Build master reference sets.
    masters = {
        code: {
            str(row.get(column, "")).strip()
            for row in accepted_rows(filename)
            if str(row.get(column, "")).strip()
        }
        for code, (filename, column) in REFERENCE_FILES.items()
    }

    # Count each row once if any required reference is unknown.
    max_invalid = int(thresholds["referential_integrity"]["max_invalid_rows"])
    for filename, columns in CHECK_FILES.items():
        invalid = 0
        for row in accepted_rows(filename):
            if any(
                str(row.get(column, "")).strip() not in masters[column]
                for column in columns
            ):
                invalid += 1
        result["referential_integrity"][filename] = {
            "invalid_rows": invalid,
            "max_invalid_rows": max_invalid,
            "passed": invalid <= max_invalid,
        }
        if invalid > max_invalid:
            reasons.append(f"{filename} has {invalid} rows with unknown master references")

    # Missing calendar days between each product/warehouse pair's first and last sale.
    sales_rows = accepted_rows("sales_history")
    pair_dates = defaultdict(set)
    for row in sales_rows:
        day = _valid_date(row.get("sale_date"))
        if day:
            pair_dates[(row.get("product_code"), row.get("warehouse_code"))].add(day)

    gaps = {
        f"{product}|{warehouse}": (max(days) - min(days)).days + 1 - len(days)
        for (product, warehouse), days in pair_dates.items()
        if days
    }
    maximum = max(gaps.values(), default=0)
    allowed = int(thresholds["sales_gaps"]["max_missing_days_per_pair"])
    result["sales_gaps"] = {
        "pairs_checked": len(gaps),
        "total_missing_days": sum(gaps.values()),
        "max_missing_days_per_pair": maximum,
        "allowed_missing_days_per_pair": allowed,
        "passed": maximum <= allowed,
    }
    if maximum > allowed:
        reasons.append(f"Sales gaps exceed limit: maximum {maximum} missing days for a pair")

    return {"trusted": not reasons, "reasons": reasons, "checks": result}


def run_quality_checks(folder, run_id, engine):
    config_path = Path(__file__).with_name("quality_thresholds.yaml")
    with config_path.open(encoding="utf-8") as stream:
        thresholds = yaml.safe_load(stream)

    with engine.connect() as connection:
        rejected = connection.execute(
            text("""
                SELECT source_file, source_row
                FROM client_ingest_rejects
                WHERE run_id = :run_id
            """),
            {"run_id": run_id},
        ).fetchall()
    rejected_rows = {
        (Path(source_file).name, int(source_row))
        for source_file, source_row in rejected
    }

    report = evaluate_quality(folder, thresholds, rejected_rows)
    reason = "; ".join(report["reasons"]) or None

    with engine.begin() as connection:
        updated = connection.execute(
            text("""
                UPDATE client_ingest_reports
                SET trusted = :trusted,
                    untrusted_reason = :reason,
                    quality_results = CAST(:results AS JSONB)
                WHERE run_id = :run_id
            """),
            {
                "trusted": report["trusted"],
                "reason": reason,
                "results": json.dumps(report["checks"]),
                "run_id": run_id,
            },
        )
        if updated.rowcount == 0:
            raise RuntimeError(f"No ingestion report rows found for run {run_id}")

    if not report["trusted"]:
        raise RuntimeError("Client data quality failed: " + reason)

    return report
