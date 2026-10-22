import csv
import math
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.supplier import Supplier


CANONICAL_SUPPLIER_ID = re.compile(r"^SUP-\d{5}$")

REQUIRED_COLUMNS = {
    "supplier_id",
    "name",
    "country",
    "city",
    "state",
    "sanctions_flag",
    "sanctions_list",
    "lead_time_days",
    "payment_terms_days",
    "reliability_score",
}

INTEGER_FIELDS = {
    "lead_time_days",
    "payment_terms_days",
}

OPTIONAL_FLOAT_FIELDS = {"lat", "lng"}

TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no"}


def _parse_finite_float(value: Any, field: str, line_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"CSV line {line_number}: invalid numeric value "
            f"for {field}: {value!r}"
        ) from exc

    if not math.isfinite(number):
        raise ValueError(
            f"CSV line {line_number}: {field} must be a finite number"
        )

    return number


def validate_supplier(
    row: dict[str, Any],
    line_number: int,
) -> dict[str, Any]:
    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column != "sanctions_list"
        and not str(row.get(column) or "").strip()
    ]

    if missing:
        raise ValueError(
            f"CSV line {line_number}: missing required values: "
            f"{', '.join(sorted(missing))}"
        )

    normalized = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()
    }

    supplier_id = str(normalized["supplier_id"])

    if not CANONICAL_SUPPLIER_ID.fullmatch(supplier_id):
        raise ValueError(
            f"CSV line {line_number}: invalid canonical supplier ID "
            f"{supplier_id!r}; expected SUP- followed by five digits"
        )

    flag = str(normalized["sanctions_flag"]).lower()

    if flag in TRUE_VALUES:
        normalized["sanctions_flag"] = True
    elif flag in FALSE_VALUES:
        normalized["sanctions_flag"] = False
    else:
        raise ValueError(
            f"CSV line {line_number}: invalid sanctions_flag "
            f"{normalized['sanctions_flag']!r}; expected true/false"
        )

    for field in INTEGER_FIELDS:
        number = _parse_finite_float(
            normalized[field], field, line_number
        )

        if number < 0 or not number.is_integer():
            raise ValueError(
                f"CSV line {line_number}: {field} must be a "
                "non-negative integer"
            )

        normalized[field] = int(number)

    normalized["reliability_score"] = _parse_finite_float(
        normalized["reliability_score"],
        "reliability_score",
        line_number,
    )

    for field in OPTIONAL_FLOAT_FIELDS:
        value = normalized.get(field)

        if value is None or not str(value).strip():
            normalized[field] = None
        else:
            normalized[field] = _parse_finite_float(
                value, field, line_number
            )

    normalized["supplier_id"] = supplier_id

    return normalized


def load_supplier_csv(
    csv_path: str | Path,
) -> list[dict[str, Any]]:
    """Read and validate supplier seed records without persisting them."""
    path = Path(csv_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Supplier seed CSV not found: {path}"
        )

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(
                "Supplier seed CSV is empty or has no header"
            )

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                "Supplier seed CSV missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        suppliers: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for line_number, row in enumerate(reader, start=2):
            if not row or not any(
                str(value or "").strip() for value in row.values()
            ):
                continue

            supplier = validate_supplier(row, line_number)
            supplier_id = supplier["supplier_id"]

            if supplier_id in seen_ids:
                raise ValueError(
                    f"CSV line {line_number}: duplicate supplier ID "
                    f"{supplier_id}"
                )

            seen_ids.add(supplier_id)
            suppliers.append(supplier)

    if not suppliers:
        raise ValueError(
            "Supplier seed CSV contains no supplier records"
        )

    return suppliers


def persist_suppliers(
    session: Session,
    records: list[dict[str, Any]],
) -> dict[str, int]:
    """Insert or update canonical supplier records.

    The caller owns the outer transaction and must commit or roll back.
    """
    inserted = 0
    updated = 0

    for record in records:
        supplier_id = record["supplier_id"]

        values = {
            "name": record["name"],
            "country": record["country"],
            "city": record["city"],
            "state": record["state"],
            "lat": record.get("lat"),
            "lng": record.get("lng"),
            "sanctions_flag": record["sanctions_flag"],
            "sanctions_list": record.get("sanctions_list") or None,
            "lead_time_days": record["lead_time_days"],
            "payment_terms_days": record["payment_terms_days"],
            "reliability_score": record["reliability_score"],
        }

        supplier = session.get(Supplier, supplier_id)

        if supplier is None:
            session.add(
                Supplier(supplier_id=supplier_id, **values)
            )
            inserted += 1
        else:
            for field, value in values.items():
                setattr(supplier, field, value)
            updated += 1

    session.flush()

    return {"inserted": inserted, "updated": updated}


def seed_suppliers(
    csv_path: str | Path,
    session: Session,
) -> dict[str, int]:
    """Validate and persist a supplier CSV inside a savepoint."""
    records = load_supplier_csv(csv_path)

    with session.begin_nested():
        return persist_suppliers(session, records)
