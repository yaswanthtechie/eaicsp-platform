"""Client staging data importer for canonical Inventory master data (R15-B8 / #324)."""

from __future__ import annotations

import csv
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.product import Product
from app.models.supplier import Supplier, SupplierLeadTime
from app.models.warehouse import Warehouse

logger = logging.getLogger(__name__)

# Canonical ID formats defined by #322 spec.yaml and Inventory conventions.
SKU_ID_RE = re.compile(r"^SKU-\d{6}$")
WAREHOUSE_ID_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
SUPPLIER_ID_RE = re.compile(r"^SUP-\d{5}$")

STAGING_TABLES = {
    "products": "stg_product_master",
    "warehouses": "stg_warehouse_master",
    "supplier_lead_times": "stg_supplier_lead_times",
}

STAGING_CSV_CANDIDATES = {
    "products": ("stg_product_master.csv", "product_master.csv"),
    "warehouses": ("stg_warehouse_master.csv", "warehouse_master.csv"),
    "supplier_lead_times": ("stg_supplier_lead_times.csv", "supplier_lead_times.csv"),
}

STAGING_DIR_ENV_VAR = "CLIENT_STAGING_DIR"
VALID_WAREHOUSE_TYPES = frozenset({"central", "regional", "local"})


class ClientImportError(Exception):
    """Base error for client staging import failures."""


class ClientImportValidationError(ClientImportError):
    """Raised when staging data violates canonical-ID, schema, or FK rules."""


@dataclass
class EntityImportCounts:
    """Counts of added, updated, and unchanged records for one entity type."""

    added: int = 0
    updated: int = 0
    unchanged: int = 0


@dataclass
class ClientImportSummary:
    """Structured result returned by client staging import runs."""

    dry_run: bool
    products: EntityImportCounts = field(default_factory=EntityImportCounts)
    warehouses: EntityImportCounts = field(default_factory=EntityImportCounts)
    supplier_lead_times: EntityImportCounts = field(default_factory=EntityImportCounts)

    def format_summary(self) -> str:
        header = (
            "Client data import - DRY RUN"
            if self.dry_run
            else "Client data import - COMPLETED"
        )
        lines = [
            header,
            "",
            "Products:",
            f"  Added: {self.products.added}",
            f"  Updated: {self.products.updated}",
            f"  Unchanged: {self.products.unchanged}",
            "",
            "Warehouses:",
            f"  Added: {self.warehouses.added}",
            f"  Updated: {self.warehouses.updated}",
            f"  Unchanged: {self.warehouses.unchanged}",
            "",
            "Supplier lead times:",
            f"  Added: {self.supplier_lead_times.added}",
            f"  Updated: {self.supplier_lead_times.updated}",
            f"  Unchanged: {self.supplier_lead_times.unchanged}",
        ]
        if self.dry_run:
            lines.extend(["", "No database changes were written."])
        return "\n".join(lines)


@dataclass
class StagingDataset:
    """In-memory staging payload aligned with #322 staging contract."""

    products: list[Mapping[str, Any]] = field(default_factory=list)
    warehouses: list[Mapping[str, Any]] = field(default_factory=list)
    supplier_lead_times: list[Mapping[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _ParsedProduct:
    sku_id: str
    values: dict[str, Any]


@dataclass(frozen=True)
class _ParsedWarehouse:
    warehouse_id: str
    values: dict[str, Any]


@dataclass(frozen=True)
class _ParsedLeadTime:
    supplier_id: str
    sku_id: str
    values: dict[str, Any]


def _pick_first(row: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any]:
    for key in keys:
        if key in row:
            return True, row[key]
    return False, None


def _has_value(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, (bool, int, float, date, datetime)):
        return True
    return str(raw).strip() != ""


def _pick_present(row: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any]:
    has_key, raw = _pick_first(row, keys)
    if not has_key or not _has_value(raw):
        return False, None
    return True, raw


def _as_clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError("expected string value, got boolean")
    return str(value).strip()


def _check_max_len(
    value: str,
    max_len: int,
    dataset: str,
    row_num: int,
    field_label: str,
) -> str:
    if len(value) > max_len:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: {field_label} longer than {max_len} characters"
        )
    return value


def _require_non_empty_str(
    row: Mapping[str, Any],
    keys: tuple[str, ...],
    dataset: str,
    row_num: int,
    field_label: str,
    *,
    max_len: int | None = None,
) -> str:
    present, raw = _pick_first(row, keys)
    if not present:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: missing required field '{field_label}'"
        )
    try:
        cleaned = _as_clean_str(raw)
    except ValueError as exc:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid value for '{field_label}': {exc}"
        ) from exc
    if not cleaned:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: empty value for required field '{field_label}'"
        )
    if max_len is not None:
        _check_max_len(cleaned, max_len, dataset, row_num, field_label)
    return cleaned


def _require_canonical_id(
    row: Mapping[str, Any],
    keys: tuple[str, ...],
    pattern: re.Pattern[str],
    dataset: str,
    row_num: int,
    field_label: str,
) -> str:
    value = _require_non_empty_str(row, keys, dataset, row_num, field_label)
    if not pattern.match(value):
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: non-canonical {field_label} "
            f"(expected format {pattern.pattern})"
        )
    return value


def _parse_non_negative_float(
    raw: Any,
    dataset: str,
    row_num: int,
    field_label: str,
) -> float:
    if isinstance(raw, bool):
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid {field_label} (boolean not allowed)"
        )
    raw_str = _as_clean_str(raw)
    if not raw_str:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: missing {field_label}"
        )
    try:
        parsed = float(raw_str)
    except ValueError as exc:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid numeric {field_label}"
        ) from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid {field_label} (must be >= 0)"
        )
    return parsed


def _parse_int_value(
    raw: Any,
    dataset: str,
    row_num: int,
    field_label: str,
    *,
    minimum: int,
) -> int:
    if isinstance(raw, bool):
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid {field_label} (boolean not allowed)"
        )
    if isinstance(raw, int):
        parsed = raw
    else:
        raw_str = _as_clean_str(raw)
        if not raw_str or not re.fullmatch(r"[+-]?\d+", raw_str):
            raise ClientImportValidationError(
                f"{dataset}[row {row_num}]: invalid integer {field_label}"
            )
        parsed = int(raw_str)
    if parsed < minimum:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid {field_label} (must be >= {minimum})"
        )
    return parsed


def _parse_bool_value(
    raw: Any,
    dataset: str,
    row_num: int,
    field_label: str,
) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    cleaned = _as_clean_str(raw).lower()
    if cleaned in {"true", "1", "yes"}:
        return True
    if cleaned in {"false", "0", "no"}:
        return False
    raise ClientImportValidationError(
        f"{dataset}[row {row_num}]: invalid boolean {field_label}"
    )


def _parse_iso_date(
    raw: Any,
    dataset: str,
    row_num: int,
    field_label: str,
) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    cleaned = _as_clean_str(raw)
    try:
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: invalid date '{field_label}' (expected YYYY-MM-DD)"
        ) from exc


def _validate_row_mapping(row: Any, dataset: str, row_num: int) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: malformed staging record (expected mapping)"
        )
    if None in row:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: malformed staging record (unexpected extra columns)"
        )
    return row


def _track_source_code_uniqueness(
    seen_codes: dict[str, str],
    row: Mapping[str, Any],
    code_keys: tuple[str, ...],
    canonical_id: str,
    dataset: str,
    row_num: int,
) -> None:
    present, raw_code = _pick_first(row, code_keys)
    if not present or raw_code is None:
        return
    code = _as_clean_str(raw_code)
    if not code:
        return
    existing_canonical = seen_codes.get(code)
    if existing_canonical is not None:
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: duplicate client source code in staging "
            f"(canonical_id={canonical_id})"
        )
    seen_codes[code] = canonical_id


def _parse_products(rows: Iterable[Mapping[str, Any]]) -> list[_ParsedProduct]:
    parsed_items: list[_ParsedProduct] = []
    seen_ids: set[str] = set()
    seen_codes: dict[str, str] = {}

    for row_num, raw_row in enumerate(rows, start=1):
        row = _validate_row_mapping(raw_row, "products", row_num)
        sku_id = _require_canonical_id(
            row, ("sku_id", "canonical_product_id"), SKU_ID_RE, "products", row_num, "sku_id"
        )
        if sku_id in seen_ids:
            raise ClientImportValidationError(
                f"products[row {row_num}]: duplicate canonical sku_id '{sku_id}' in staging"
            )
        seen_ids.add(sku_id)
        _track_source_code_uniqueness(
            seen_codes, row, ("product_code", "client_product_code"), sku_id, "products", row_num
        )

        name = _require_non_empty_str(
            row,
            ("product_name", "name"),
            "products",
            row_num,
            "product_name",
            max_len=255,
        )
        category = _require_non_empty_str(
            row, ("category",), "products", row_num, "category", max_len=64
        )
        unit_of_measure = _require_non_empty_str(
            row,
            ("unit_of_measure", "unit"),
            "products",
            row_num,
            "unit_of_measure",
            max_len=32,
        )

        has_price, raw_price = _pick_present(row, ("unit_price",))
        if not has_price:
            raise ClientImportValidationError(
                f"products[row {row_num}]: missing required unit_price for '{sku_id}'"
            )

        values: dict[str, Any] = {
            "name": name,
            "category": category,
            "unit_of_measure": unit_of_measure,
            "unit_price": _parse_non_negative_float(
                raw_price, "products", row_num, "unit_price"
            ),
        }

        has_cost, raw_cost = _pick_present(row, ("unit_cost",))
        if has_cost:
            values["unit_cost"] = _parse_non_negative_float(
                raw_cost, "products", row_num, "unit_cost"
            )

        has_active, raw_active = _pick_present(row, ("is_active",))
        if has_active:
            values["is_active"] = _parse_bool_value(
                raw_active, "products", row_num, "is_active"
            )

        has_sup, _ = _pick_present(row, ("supplier_id",))
        if has_sup:
            values["supplier_id"] = _require_canonical_id(
                row, ("supplier_id",), SUPPLIER_ID_RE, "products", row_num, "supplier_id"
            )

        parsed_items.append(_ParsedProduct(sku_id=sku_id, values=values))

    return parsed_items


def _parse_warehouses(rows: Iterable[Mapping[str, Any]]) -> list[_ParsedWarehouse]:
    parsed_items: list[_ParsedWarehouse] = []
    seen_ids: set[str] = set()
    seen_codes: dict[str, str] = {}

    for row_num, raw_row in enumerate(rows, start=1):
        row = _validate_row_mapping(raw_row, "warehouses", row_num)
        warehouse_id = _require_canonical_id(
            row,
            ("warehouse_id", "canonical_warehouse_id"),
            WAREHOUSE_ID_RE,
            "warehouses",
            row_num,
            "warehouse_id",
        )
        if warehouse_id in seen_ids:
            raise ClientImportValidationError(
                f"warehouses[row {row_num}]: duplicate canonical warehouse_id '{warehouse_id}' in staging"
            )
        seen_ids.add(warehouse_id)
        _track_source_code_uniqueness(
            seen_codes,
            row,
            ("warehouse_code", "client_warehouse_code"),
            warehouse_id,
            "warehouses",
            row_num,
        )

        values: dict[str, Any] = {
            "name": _require_non_empty_str(
                row,
                ("warehouse_name", "name"),
                "warehouses",
                row_num,
                "warehouse_name",
                max_len=255,
            ),
            "city": _require_non_empty_str(
                row, ("city",), "warehouses", row_num, "city", max_len=64
            ),
            "state": _require_non_empty_str(
                row, ("state",), "warehouses", row_num, "state", max_len=64
            ),
            "country": _require_non_empty_str(
                row, ("country",), "warehouses", row_num, "country", max_len=64
            ),
        }

        has_pin, raw_pin = _pick_present(row, ("pincode",))
        if has_pin:
            values["pincode"] = _check_max_len(
                _as_clean_str(raw_pin), 16, "warehouses", row_num, "pincode"
            )

        has_type, raw_type = _pick_present(row, ("warehouse_type",))
        if has_type:
            warehouse_type = _check_max_len(
                _as_clean_str(raw_type).lower(),
                32,
                "warehouses",
                row_num,
                "warehouse_type",
            )
            if warehouse_type not in VALID_WAREHOUSE_TYPES:
                raise ClientImportValidationError(
                    f"warehouses[row {row_num}]: invalid warehouse_type"
                )
            values["warehouse_type"] = warehouse_type

        has_cap, raw_cap = _pick_present(row, ("capacity_units",))
        if has_cap:
            values["capacity_units"] = _parse_int_value(
                raw_cap, "warehouses", row_num, "capacity_units", minimum=0
            )

        parsed_items.append(_ParsedWarehouse(warehouse_id=warehouse_id, values=values))

    return parsed_items


def _parse_supplier_lead_times(
    rows: Iterable[Mapping[str, Any]],
) -> list[_ParsedLeadTime]:
    parsed_items: list[_ParsedLeadTime] = []
    seen_pairs: set[tuple[str, str]] = set()

    for row_num, raw_row in enumerate(rows, start=1):
        row = _validate_row_mapping(raw_row, "supplier_lead_times", row_num)
        supplier_id = _require_canonical_id(
            row,
            ("supplier_id", "canonical_supplier_id"),
            SUPPLIER_ID_RE,
            "supplier_lead_times",
            row_num,
            "supplier_id",
        )
        sku_id = _require_canonical_id(
            row,
            ("sku_id", "canonical_product_id"),
            SKU_ID_RE,
            "supplier_lead_times",
            row_num,
            "sku_id",
        )
        pair = (supplier_id, sku_id)
        if pair in seen_pairs:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: duplicate canonical key "
                f"({supplier_id}, {sku_id}) in staging"
            )
        seen_pairs.add(pair)

        has_avg, raw_avg = _pick_present(
            row, ("average_lead_time_days", "lead_time_days")
        )
        if not has_avg:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: missing average_lead_time_days"
            )
        avg_days = _parse_int_value(
            raw_avg, "supplier_lead_times", row_num, "average_lead_time_days", minimum=1
        )

        min_days = None
        has_min, raw_min = _pick_present(row, ("minimum_lead_time_days",))
        if has_min:
            min_days = _parse_int_value(
                raw_min, "supplier_lead_times", row_num, "minimum_lead_time_days", minimum=1
            )

        max_days = None
        has_max, raw_max = _pick_present(row, ("maximum_lead_time_days",))
        if has_max:
            max_days = _parse_int_value(
                raw_max, "supplier_lead_times", row_num, "maximum_lead_time_days", minimum=1
            )

        if min_days is not None and min_days > avg_days:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: minimum_lead_time_days exceeds average_lead_time_days"
            )
        if max_days is not None and max_days < avg_days:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: maximum_lead_time_days below average_lead_time_days"
            )
        if min_days is not None and max_days is not None and min_days > max_days:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: minimum_lead_time_days exceeds maximum_lead_time_days"
            )

        eff_date = None
        has_eff, raw_eff = _pick_present(row, ("effective_date",))
        if has_eff:
            eff_date = _parse_iso_date(
                raw_eff, "supplier_lead_times", row_num, "effective_date"
            )

        parsed_items.append(
            _ParsedLeadTime(
                supplier_id=supplier_id,
                sku_id=sku_id,
                values={
                    "average_lead_time_days": avg_days,
                    "minimum_lead_time_days": min_days,
                    "maximum_lead_time_days": max_days,
                    "effective_date": eff_date,
                },
            )
        )

    return parsed_items


def _values_equal(current: Any, incoming: Any) -> bool:
    if isinstance(current, float) or isinstance(incoming, float):
        if current is None or incoming is None:
            return current is incoming
        return math.isclose(float(current), float(incoming), rel_tol=0.0, abs_tol=1e-9)
    return current == incoming


def _upsert_mapped_records(
    db: Session,
    existing_map: dict[Any, Any],
    items: Iterable[tuple[Any, Callable[[], Any], dict[str, Any]]],
    dry_run: bool,
) -> EntityImportCounts:
    """Generic idempotent diff/upsert engine for canonical-keyed Inventory models."""
    counts = EntityImportCounts()
    for key, build_insert_obj, update_fields in items:
        existing_obj = existing_map.get(key)
        if existing_obj is None:
            counts.added += 1
            if not dry_run:
                new_obj = build_insert_obj()
                db.add(new_obj)
                existing_map[key] = new_obj
            continue

        changed = {
            field_name: new_val
            for field_name, new_val in update_fields.items()
            if not _values_equal(getattr(existing_obj, field_name), new_val)
        }
        if not changed:
            counts.unchanged += 1
            continue

        counts.updated += 1
        if not dry_run:
            for field_name, new_val in changed.items():
                setattr(existing_obj, field_name, new_val)

    return counts


def _apply_products(
    db: Session,
    parsed: list[_ParsedProduct],
    existing: dict[str, Product],
    dry_run: bool,
) -> EntityImportCounts:
    plan = []
    for item in parsed:
        existing_obj = existing.get(item.sku_id)
        if existing_obj is None and "unit_cost" not in item.values:
            raise ClientImportValidationError(
                f"products: new sku_id '{item.sku_id}' has no unit_cost in staging"
            )
        insert_vals = dict(item.values)
        insert_vals.setdefault("is_active", True)

        update_vals = {
            key: item.values[key]
            for key in (
                "name",
                "category",
                "unit_of_measure",
                "unit_price",
                "unit_cost",
                "is_active",
                "supplier_id",
            )
            if key in item.values
        }

        plan.append(
            (
                item.sku_id,
                lambda sku=item.sku_id, v=insert_vals: Product(sku_id=sku, **v),
                update_vals,
            )
        )
    return _upsert_mapped_records(db, existing, plan, dry_run=dry_run)


def _apply_warehouses(
    db: Session,
    parsed: list[_ParsedWarehouse],
    dry_run: bool,
) -> EntityImportCounts:
    existing = {row.warehouse_id: row for row in db.query(Warehouse).all()}
    plan = []
    for item in parsed:
        insert_vals = dict(item.values)
        insert_vals.setdefault("capacity_units", 0)
        insert_vals.setdefault("warehouse_type", "central")
        plan.append(
            (
                item.warehouse_id,
                lambda wh=item.warehouse_id, v=insert_vals: Warehouse(warehouse_id=wh, **v),
                dict(item.values),
            )
        )
    return _upsert_mapped_records(db, existing, plan, dry_run=dry_run)


def _apply_lead_times(
    db: Session,
    parsed: list[_ParsedLeadTime],
    valid_supplier_ids: set[str],
    valid_sku_ids: set[str],
    dry_run: bool,
) -> EntityImportCounts:
    for idx, item in enumerate(parsed, start=1):
        if item.supplier_id not in valid_supplier_ids:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {idx}]: unknown supplier_id "
                f"'{item.supplier_id}' (missing foreign key in suppliers)"
            )
        if item.sku_id not in valid_sku_ids:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {idx}]: unknown sku_id "
                f"'{item.sku_id}' (missing foreign key in products)"
            )

    existing = {
        (row.supplier_id, row.sku_id): row
        for row in db.query(SupplierLeadTime).all()
    }
    plan = []
    for item in parsed:
        key = (item.supplier_id, item.sku_id)
        vals = dict(item.values)
        plan.append(
            (
                key,
                lambda sid=item.supplier_id, sku=item.sku_id, v=vals: SupplierLeadTime(
                    supplier_id=sid, sku_id=sku, **v
                ),
                vals,
            )
        )
    return _upsert_mapped_records(db, existing, plan, dry_run=dry_run)


def import_staging_dataset(
    db: Session,
    dataset: StagingDataset,
    *,
    dry_run: bool = False,
) -> ClientImportSummary:
    """Validate and upsert canonical staging records in a single transaction."""
    parsed_products = _parse_products(dataset.products)
    parsed_warehouses = _parse_warehouses(dataset.warehouses)
    parsed_lead_times = _parse_supplier_lead_times(dataset.supplier_lead_times)

    valid_supplier_ids = {row[0] for row in db.query(Supplier.supplier_id).all()}
    existing_products = {row.sku_id: row for row in db.query(Product).all()}
    valid_sku_ids = set(existing_products) | {p.sku_id for p in parsed_products}

    for idx, item in enumerate(parsed_products, start=1):
        supplier_id = item.values.get("supplier_id")
        if supplier_id is not None and supplier_id not in valid_supplier_ids:
            raise ClientImportValidationError(
                f"products[row {idx}]: unknown supplier_id '{supplier_id}' (not in suppliers)"
            )

    try:
        product_counts = _apply_products(
            db, parsed_products, existing_products, dry_run=dry_run
        )
        warehouse_counts = _apply_warehouses(db, parsed_warehouses, dry_run=dry_run)
        if not dry_run:
            db.flush()
        lead_time_counts = _apply_lead_times(
            db,
            parsed_lead_times,
            valid_supplier_ids=valid_supplier_ids,
            valid_sku_ids=valid_sku_ids,
            dry_run=dry_run,
        )
        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise

    summary = ClientImportSummary(
        dry_run=dry_run,
        products=product_counts,
        warehouses=warehouse_counts,
        supplier_lead_times=lead_time_counts,
    )
    logger.info(
        "Client data import (%s): products=+%d/~%d/=%d, warehouses=+%d/~%d/=%d, lead_times=+%d/~%d/=%d",
        "dry-run" if dry_run else "committed",
        summary.products.added,
        summary.products.updated,
        summary.products.unchanged,
        summary.warehouses.added,
        summary.warehouses.updated,
        summary.warehouses.unchanged,
        summary.supplier_lead_times.added,
        summary.supplier_lead_times.updated,
        summary.supplier_lead_times.unchanged,
    )
    return summary


def _resolve_csv_file(staging_dir: Path, entity: str, *, required: bool) -> Path | None:
    for filename in STAGING_CSV_CANDIDATES[entity]:
        candidate = staging_dir / filename
        if candidate.is_file():
            return candidate
    if required:
        expected = " or ".join(STAGING_CSV_CANDIDATES[entity])
        raise ClientImportError(
            f"Missing required staging CSV for '{entity}' in staging directory "
            f"(expected {expected})"
        )
    return None


def _read_csv_records(path: Path, dataset: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ClientImportValidationError(
                f"{dataset}: CSV file has no header row"
            )
        return list(reader)


def load_staging_dataset_from_dir(staging_dir: Path | str) -> StagingDataset:
    """Load canonical client staging CSVs from a local staging directory."""
    resolved = Path(staging_dir).resolve()
    if not resolved.is_dir():
        raise ClientImportError(f"Staging directory does not exist: {resolved}")

    prod_path = _resolve_csv_file(resolved, "products", required=True)
    wh_path = _resolve_csv_file(resolved, "warehouses", required=True)
    lt_path = _resolve_csv_file(resolved, "supplier_lead_times", required=True)

    return StagingDataset(
        products=_read_csv_records(prod_path, "products") if prod_path else [],
        warehouses=_read_csv_records(wh_path, "warehouses") if wh_path else [],
        supplier_lead_times=_read_csv_records(lt_path, "supplier_lead_times") if lt_path else [],
    )


def _load_table_rows(db: Session, table_name: str, *, required: bool) -> list[dict[str, Any]]:
    conn = db.connection()
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        if required:
            raise ClientImportError(
                f"Required staging table '{table_name}' does not exist in database"
            )
        return []
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=conn)
    rows = conn.execute(select(table)).mappings().all()
    return [dict(row) for row in rows]


def load_staging_dataset_from_db(db: Session) -> StagingDataset:
    """Read client staging tables from Inventory's configured database."""
    return StagingDataset(
        products=_load_table_rows(db, STAGING_TABLES["products"], required=True),
        warehouses=_load_table_rows(db, STAGING_TABLES["warehouses"], required=True),
        supplier_lead_times=_load_table_rows(
            db, STAGING_TABLES["supplier_lead_times"], required=True
        ),
    )


def _db_has_staging_tables(db: Session) -> bool:
    conn = db.connection()
    inspector = inspect(conn)
    required = (
        STAGING_TABLES["products"],
        STAGING_TABLES["warehouses"],
        STAGING_TABLES["supplier_lead_times"],
    )
    return all(inspector.has_table(name) for name in required)


def run_client_data_import(
    *,
    db: Session | None = None,
    staging_dir: Path | str | None = None,
    source: str = "auto",
    dry_run: bool = False,
) -> ClientImportSummary:
    """Resolve the staging source and execute client data import."""
    if source not in {"auto", "csv", "db"}:
        raise ClientImportError(f"Unsupported staging source '{source}'")

    configured_dir = staging_dir or os.getenv(STAGING_DIR_ENV_VAR)
    session = db or SessionLocal()
    try:
        if source == "csv":
            if not configured_dir:
                raise ClientImportError(
                    "CSV staging source requested, but neither --staging-dir "
                    f"nor {STAGING_DIR_ENV_VAR} was provided"
                )
            dataset = load_staging_dataset_from_dir(configured_dir)
        elif source == "db":
            dataset = load_staging_dataset_from_db(session)
        else:
            if configured_dir:
                dataset = load_staging_dataset_from_dir(configured_dir)
            elif _db_has_staging_tables(session):
                dataset = load_staging_dataset_from_db(session)
            else:
                raise ClientImportError(
                    "No client staging source found. Pass --staging-dir <path>, "
                    f"set {STAGING_DIR_ENV_VAR}, or populate staging tables "
                    "(stg_product_master, stg_warehouse_master, stg_supplier_lead_times)."
                )

        return import_staging_dataset(session, dataset, dry_run=dry_run)
    finally:
        if db is None:
            session.close()
