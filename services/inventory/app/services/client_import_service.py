"""Client staging data importer for canonical Inventory master data (R15-B8 / #324)."""

from __future__ import annotations

import csv
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SAFETY_STOCK, settings
from app.database import SessionLocal
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier, SupplierLeadTime
from app.models.warehouse import Warehouse
from app.services.purchase_order_service import select_supplier
from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
)
from app.services.supplier_performance_service import (
    calculate_all_suppliers_performance,
)

logger = logging.getLogger(__name__)

# Canonical ID formats defined by #322 spec.yaml and Inventory conventions.
SKU_ID_RE = re.compile(r"^SKU-\d{6}$")
WAREHOUSE_ID_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
SUPPLIER_ID_RE = re.compile(r"^SUP-\d{5}$")
PO_ID_RE = re.compile(r"^PO-\d{4}-\d{6}$")

STAGING_TABLES = {
    "products": "stg_product_master",
    "warehouses": "stg_warehouse_master",
    "supplier_lead_times": "stg_supplier_lead_times",
    "inventory_snapshots": "stg_inventory_snapshot",
    "purchase_order_history": "stg_purchase_order_history",
}

STAGING_CSV_CANDIDATES = {
    "products": ("stg_product_master.csv", "product_master.csv"),
    "warehouses": ("stg_warehouse_master.csv", "warehouse_master.csv"),
    "supplier_lead_times": ("stg_supplier_lead_times.csv", "supplier_lead_times.csv"),
    "inventory_snapshots": ("stg_inventory_snapshot.csv", "inventory_snapshot.csv"),
    "purchase_order_history": (
        "stg_purchase_order_history.csv",
        "purchase_order_history.csv",
    ),
}

VALID_WAREHOUSE_TYPES = frozenset({"central", "regional", "local"})
VALID_PO_STATUSES = frozenset({"open", "received", "cancelled"})


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
class SnapshotImportRecord:
    """Audit record for an imported inventory snapshot entry."""

    sku_id: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    reorder_point_source: str  # "imported" or "calculated"
    safety_stock: int
    safety_stock_source: str  # "imported" or "default"
    fallback_reason: str | None = None


@dataclass
class SupplierPerformanceSummary:
    """Summary of on-time delivery metrics for a supplier."""

    supplier_id: str
    supplier_name: str | None
    received_po_count: int
    on_time_po_count: int
    on_time_delivery_percent: float | None
    total_po_count: int = 0
    open_po_count: int = 0
    cancelled_po_count: int = 0
    late_po_count: int = 0
    unverified_po_count: int = 0


@dataclass
class ReorderSummaryItem:
    """Reorder recommendation output item for an inventory SKU/warehouse."""

    sku_id: str
    product_name: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int
    safety_stock: int
    needs_reorder: bool
    suggested_quantity: int
    supplier_id: str
    supplier_name: str
    unit_cost: float
    expected_cost: float
    supplier_on_time_percent: float | None = None
    reorder_point_source: str = "imported"
    safety_stock_source: str = "imported"
    fallback_reason: str | None = None


@dataclass
class ClientImportSummary:
    """Structured result returned by client staging import runs."""

    dry_run: bool
    products: EntityImportCounts = field(default_factory=EntityImportCounts)
    warehouses: EntityImportCounts = field(default_factory=EntityImportCounts)
    supplier_lead_times: EntityImportCounts = field(default_factory=EntityImportCounts)
    inventory_snapshots: EntityImportCounts = field(default_factory=EntityImportCounts)
    purchase_order_history: EntityImportCounts = field(
        default_factory=EntityImportCounts
    )
    snapshot_records: list[SnapshotImportRecord] = field(default_factory=list)
    supplier_performance: list[SupplierPerformanceSummary] = field(default_factory=list)
    reorder_recommendations: list[ReorderSummaryItem] = field(default_factory=list)

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

        if (
            self.inventory_snapshots.added
            or self.inventory_snapshots.updated
            or self.inventory_snapshots.unchanged
            or self.snapshot_records
        ):
            lines.extend(
                [
                    "",
                    "Inventory snapshots:",
                    f"  Added: {self.inventory_snapshots.added}",
                    f"  Updated: {self.inventory_snapshots.updated}",
                    f"  Unchanged: {self.inventory_snapshots.unchanged}",
                ]
            )
            imp_rop = sum(
                1 for r in self.snapshot_records if r.reorder_point_source == "imported"
            )
            calc_rop = sum(
                1
                for r in self.snapshot_records
                if r.reorder_point_source == "calculated"
            )
            imp_ss = sum(
                1 for r in self.snapshot_records if r.safety_stock_source == "imported"
            )
            default_ss = sum(
                1 for r in self.snapshot_records if r.safety_stock_source == "default"
            )
            lines.extend(
                [
                    f"  Reorder points: imported={imp_rop}, calculated_fallback={calc_rop}",
                    f"  Safety stocks: imported={imp_ss}, default_fallback={default_ss}",
                ]
            )

        if (
            self.purchase_order_history.added
            or self.purchase_order_history.updated
            or self.purchase_order_history.unchanged
        ):
            lines.extend(
                [
                    "",
                    "Purchase orders:",
                    f"  Added: {self.purchase_order_history.added}",
                    f"  Updated: {self.purchase_order_history.updated}",
                    f"  Unchanged: {self.purchase_order_history.unchanged}",
                ]
            )

        if self.supplier_performance:
            lines.extend(["", "Supplier on-time delivery performance:"])
            for sp in self.supplier_performance:
                percent = (
                    f"{sp.on_time_delivery_percent:.1f}%"
                    if sp.on_time_delivery_percent is not None
                    else "n/a (no dated Received POs)"
                )
                lines.append(
                    f"  {sp.supplier_id} ({sp.supplier_name or 'Unknown'}): {percent} "
                    f"(Received: {sp.received_po_count}, On-time: {sp.on_time_po_count}, "
                    f"Unverified: {sp.unverified_po_count}; "
                    f"Open: {sp.open_po_count}, Cancelled: {sp.cancelled_po_count} ignored)"
                )

        if self.reorder_recommendations:
            lines.extend(["", "Reorder recommendations:"])
            for rec in self.reorder_recommendations:
                if rec.needs_reorder:
                    lines.append(
                        f"  {rec.sku_id} at {rec.warehouse_id}: QOH={rec.quantity_on_hand}, "
                        f"ROP={rec.reorder_point} -> Reorder {rec.suggested_quantity} units "
                        f"from {rec.supplier_id} (est. spend: {rec.expected_cost:.2f})"
                    )

        if self.dry_run:
            lines.extend(["", "No database changes were written."])
        return "\n".join(lines)


@dataclass
class StagingDataset:
    """In-memory staging payload aligned with #322 staging contract."""

    products: Sequence[Mapping[str, Any]] = field(default_factory=list)
    warehouses: Sequence[Mapping[str, Any]] = field(default_factory=list)
    supplier_lead_times: Sequence[Mapping[str, Any]] = field(default_factory=list)
    inventory_snapshots: Sequence[Mapping[str, Any]] = field(default_factory=list)
    purchase_order_history: Sequence[Mapping[str, Any]] = field(default_factory=list)


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


@dataclass(frozen=True)
class _ParsedSnapshot:
    sku_id: str
    warehouse_id: str
    quantity_on_hand: int
    reorder_point: int | None
    safety_stock: int | None
    snapshot_date: date | None


@dataclass(frozen=True)
class _ParsedPurchaseOrder:
    po_id: str
    sku_id: str
    warehouse_id: str
    supplier_id: str
    order_date: date
    expected_date: date
    received_date: date | None
    quantity_ordered: int
    unit_cost: float
    po_status: str


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
    for key in keys:
        if key in row and _has_value(row[key]):
            return True, row[key]
    return False, None


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
    present, raw = _pick_present(row, keys)
    if not present:
        has_key, _ = _pick_first(row, keys)
        reason = (
            "empty value for required field" if has_key else "missing required field"
        )
        raise ClientImportValidationError(
            f"{dataset}[row {row_num}]: {reason} '{field_label}'"
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


def _resolve_sku_id(row: Mapping[str, Any], dataset: str, row_num: int) -> str:
    return _require_canonical_id(
        row, ("sku_id",), SKU_ID_RE, dataset, row_num, "sku_id"
    )


def _resolve_warehouse_id(row: Mapping[str, Any], dataset: str, row_num: int) -> str:
    return _require_canonical_id(
        row, ("warehouse_id",), WAREHOUSE_ID_RE, dataset, row_num, "warehouse_id"
    )


def _resolve_supplier_id(row: Mapping[str, Any], dataset: str, row_num: int) -> str:
    return _require_canonical_id(
        row, ("supplier_id",), SUPPLIER_ID_RE, dataset, row_num, "supplier_id"
    )


def _resolve_po_id(row: Mapping[str, Any], dataset: str, row_num: int) -> str:
    return _require_canonical_id(row, ("po_id",), PO_ID_RE, dataset, row_num, "po_id")


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
            row,
            ("sku_id", "canonical_product_id"),
            SKU_ID_RE,
            "products",
            row_num,
            "sku_id",
        )
        if sku_id in seen_ids:
            raise ClientImportValidationError(
                f"products[row {row_num}]: duplicate canonical sku_id '{sku_id}' in staging"
            )
        seen_ids.add(sku_id)
        _track_source_code_uniqueness(
            seen_codes,
            row,
            ("product_code", "client_product_code"),
            sku_id,
            "products",
            row_num,
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
                row,
                ("supplier_id",),
                SUPPLIER_ID_RE,
                "products",
                row_num,
                "supplier_id",
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

        pincode = _require_non_empty_str(
            row, ("pincode",), "warehouses", row_num, "pincode", max_len=16
        )
        if not re.fullmatch(r"\d{6}", pincode):
            raise ClientImportValidationError(
                f"warehouses[row {row_num}]: pincode must be 6 digits"
            )
        values["pincode"] = pincode

        warehouse_type = _require_non_empty_str(
            row,
            ("warehouse_type",),
            "warehouses",
            row_num,
            "warehouse_type",
            max_len=32,
        ).lower()
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

        has_min, raw_min = _pick_present(row, ("minimum_lead_time_days",))
        if not has_min:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: missing minimum_lead_time_days"
            )
        min_days = _parse_int_value(
            raw_min, "supplier_lead_times", row_num, "minimum_lead_time_days", minimum=1
        )

        has_max, raw_max = _pick_present(row, ("maximum_lead_time_days",))
        if not has_max:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: missing maximum_lead_time_days"
            )
        max_days = _parse_int_value(
            raw_max, "supplier_lead_times", row_num, "maximum_lead_time_days", minimum=1
        )

        if not min_days <= avg_days <= max_days:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: lead times must satisfy "
                "minimum <= average <= maximum"
            )

        has_eff, raw_eff = _pick_present(row, ("effective_date",))
        if not has_eff:
            raise ClientImportValidationError(
                f"supplier_lead_times[row {row_num}]: missing effective_date"
            )
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


def _parse_inventory_snapshots(
    rows: Iterable[Mapping[str, Any]],
) -> list[_ParsedSnapshot]:
    parsed_items: list[_ParsedSnapshot] = []
    seen_keys: set[tuple[str, str]] = set()

    for row_num, raw_row in enumerate(rows, start=1):
        row = _validate_row_mapping(raw_row, "inventory_snapshots", row_num)
        sku_id = _resolve_sku_id(row, "inventory_snapshots", row_num)
        warehouse_id = _resolve_warehouse_id(row, "inventory_snapshots", row_num)

        key = (sku_id, warehouse_id)
        if key in seen_keys:
            raise ClientImportValidationError(
                f"inventory_snapshots[row {row_num}]: duplicate canonical key "
                f"({sku_id}, {warehouse_id}) in staging"
            )
        seen_keys.add(key)

        has_qoh, raw_qoh = _pick_present(row, ("quantity_on_hand", "qoh"))
        if not has_qoh:
            raise ClientImportValidationError(
                f"inventory_snapshots[row {row_num}]: missing required field 'quantity_on_hand'"
            )
        qoh = _parse_int_value(
            raw_qoh, "inventory_snapshots", row_num, "quantity_on_hand", minimum=0
        )

        has_rop, raw_rop = _pick_present(row, ("reorder_point", "rop"))
        rop: int | None = None
        if has_rop:
            rop = _parse_int_value(
                raw_rop, "inventory_snapshots", row_num, "reorder_point", minimum=0
            )

        has_ss, raw_ss = _pick_present(row, ("safety_stock",))
        safety_stock: int | None = None
        if has_ss:
            safety_stock = _parse_int_value(
                raw_ss, "inventory_snapshots", row_num, "safety_stock", minimum=0
            )

        has_date, raw_date = _pick_present(row, ("snapshot_date",))
        snap_date = (
            _parse_iso_date(raw_date, "inventory_snapshots", row_num, "snapshot_date")
            if has_date
            else None
        )

        parsed_items.append(
            _ParsedSnapshot(
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                quantity_on_hand=qoh,
                reorder_point=rop,
                safety_stock=safety_stock,
                snapshot_date=snap_date,
            )
        )

    return parsed_items


def _parse_purchase_order_history(
    rows: Iterable[Mapping[str, Any]],
) -> list[_ParsedPurchaseOrder]:
    parsed_items: list[_ParsedPurchaseOrder] = []
    seen_po_ids: set[str] = set()

    for row_num, raw_row in enumerate(rows, start=1):
        row = _validate_row_mapping(raw_row, "purchase_order_history", row_num)

        has_od, raw_od = _pick_present(row, ("order_date",))
        if not has_od:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: missing required field 'order_date'"
            )
        order_date = _parse_iso_date(
            raw_od, "purchase_order_history", row_num, "order_date"
        )

        has_ed, raw_ed = _pick_present(row, ("expected_date",))
        if not has_ed:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: missing required field 'expected_date'"
            )
        expected_date = _parse_iso_date(
            raw_ed, "purchase_order_history", row_num, "expected_date"
        )

        raw_status = _require_non_empty_str(
            row, ("po_status", "status"), "purchase_order_history", row_num, "po_status"
        ).lower()
        if raw_status not in VALID_PO_STATUSES:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: invalid po_status '{raw_status}' "
                "(expected Open, Received, or Cancelled)"
            )

        po_id = _resolve_po_id(row, "purchase_order_history", row_num)
        if po_id in seen_po_ids:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: duplicate canonical po_id '{po_id}' in staging"
            )
        seen_po_ids.add(po_id)

        sku_id = _resolve_sku_id(row, "purchase_order_history", row_num)
        warehouse_id = _resolve_warehouse_id(row, "purchase_order_history", row_num)
        supplier_id = _resolve_supplier_id(row, "purchase_order_history", row_num)

        has_qty, raw_qty = _pick_present(row, ("quantity_ordered", "quantity"))
        if not has_qty:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: missing required field 'quantity_ordered'"
            )
        qty = _parse_int_value(
            raw_qty, "purchase_order_history", row_num, "quantity_ordered", minimum=1
        )

        has_cost, raw_cost = _pick_present(row, ("unit_cost",))
        if not has_cost:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: missing required field 'unit_cost'"
            )
        unit_cost = _parse_non_negative_float(
            raw_cost, "purchase_order_history", row_num, "unit_cost"
        )

        has_rd, raw_rd = _pick_present(row, ("received_date",))
        received_date: date | None = None
        if raw_status == "received":
            if not has_rd:
                raise ClientImportValidationError(
                    f"purchase_order_history[row {row_num}]: missing received_date for Received PO '{po_id}'"
                )
            received_date = _parse_iso_date(
                raw_rd, "purchase_order_history", row_num, "received_date"
            )
        else:
            if has_rd:
                received_date = _parse_iso_date(
                    raw_rd, "purchase_order_history", row_num, "received_date"
                )

        if expected_date < order_date:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: expected_date {expected_date} "
                f"is before order_date {order_date}"
            )
        if received_date is not None and received_date < order_date:
            raise ClientImportValidationError(
                f"purchase_order_history[row {row_num}]: received_date {received_date} "
                f"is before order_date {order_date}"
            )

        parsed_items.append(
            _ParsedPurchaseOrder(
                po_id=po_id,
                sku_id=sku_id,
                warehouse_id=warehouse_id,
                supplier_id=supplier_id,
                order_date=order_date,
                expected_date=expected_date,
                received_date=received_date,
                quantity_ordered=qty,
                unit_cost=unit_cost,
                po_status=raw_status,
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
        plan.append(
            (
                item.warehouse_id,
                lambda wh=item.warehouse_id, v=insert_vals: Warehouse(
                    warehouse_id=wh, **v
                ),
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
        (row.supplier_id, row.sku_id): row for row in db.query(SupplierLeadTime).all()
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


def _apply_inventory_snapshots(
    db: Session,
    parsed: list[_ParsedSnapshot],
    valid_sku_ids: set[str],
    valid_warehouse_ids: set[str],
    products_by_id: dict[str, Product],
    dry_run: bool,
) -> tuple[EntityImportCounts, list[SnapshotImportRecord]]:
    for idx, item in enumerate(parsed, start=1):
        if item.sku_id not in valid_sku_ids:
            raise ClientImportValidationError(
                f"inventory_snapshots[row {idx}]: unknown sku_id '{item.sku_id}' (missing foreign key in products)"
            )
        if item.warehouse_id not in valid_warehouse_ids:
            raise ClientImportValidationError(
                f"inventory_snapshots[row {idx}]: unknown warehouse_id '{item.warehouse_id}' (missing foreign key in warehouses)"
            )

    existing = {
        (row.sku_id, row.warehouse_id): row for row in db.query(Inventory).all()
    }
    warehouses_by_id = {w.warehouse_id: w for w in db.query(Warehouse).all()}
    lead_times_by_sku = {
        lt.sku_id: lt.average_lead_time_days for lt in db.query(SupplierLeadTime).all()
    }

    counts = EntityImportCounts()
    snapshot_records: list[SnapshotImportRecord] = []
    reorder_context = None

    for item in parsed:
        key = (item.sku_id, item.warehouse_id)
        existing_obj = existing.get(key)
        wh_obj = warehouses_by_id.get(item.warehouse_id)
        wh_type = (
            wh_obj.warehouse_type if (wh_obj and wh_obj.warehouse_type) else "local"
        )

        # 1. Resolve safety stock (provided vs default fallback)
        if item.safety_stock is not None:
            ss_val = item.safety_stock
            ss_source = "imported"
            ss_fallback = None
        else:
            ss_val = (
                existing_obj.safety_stock
                if existing_obj is not None
                else DEFAULT_SAFETY_STOCK
            )
            ss_source = "default"
            ss_fallback = "missing from client snapshot"

        # 2. Resolve lead time
        lead_time = (
            existing_obj.lead_time_days
            if existing_obj is not None
            else lead_times_by_sku.get(item.sku_id, 7)
        )

        # 3. Resolve reorder point (provided vs calculated fallback)
        if item.reorder_point is not None:
            rop_val = item.reorder_point
            rop_source = "imported"
            rop_fallback = None
        else:
            if reorder_context is None:
                reorder_context = build_reorder_context(db)
            stub_obj = {
                "sku_id": item.sku_id,
                "warehouse_id": item.warehouse_id,
                "quantity_on_hand": item.quantity_on_hand,
                "lead_time_days": lead_time,
                "safety_stock": ss_val,
            }
            calc = calculate_reorder_point(db, stub_obj, context=reorder_context)
            rop_val = calc["reorder_point"]
            rop_source = "calculated"
            rop_fallback = "missing from client snapshot"

        fallback_reason = rop_fallback or ss_fallback

        # Store only a client-provided reorder point. A calculated one stays
        # None in the database so calculate_reorder_point() keeps recalculating
        # it from current demand and lead time.
        stored_rop = item.reorder_point

        record = SnapshotImportRecord(
            sku_id=item.sku_id,
            warehouse_id=item.warehouse_id,
            quantity_on_hand=item.quantity_on_hand,
            reorder_point=rop_val,
            reorder_point_source=rop_source,
            safety_stock=ss_val,
            safety_stock_source=ss_source,
            fallback_reason=fallback_reason,
        )
        snapshot_records.append(record)

        if existing_obj is None:
            counts.added += 1
            if not dry_run:
                prod = products_by_id.get(item.sku_id)
                new_inv = Inventory(
                    sku_id=item.sku_id,
                    warehouse_id=item.warehouse_id,
                    product_name=prod.name if prod else f"Product {item.sku_id}",
                    category=prod.category if prod else "Uncategorized",
                    quantity_on_hand=item.quantity_on_hand,
                    safety_stock=ss_val,
                    reorder_point=stored_rop,
                    lead_time_days=lead_time,
                    warehouse_type=wh_type,
                    version=1,
                )
                db.add(new_inv)
                existing[key] = new_inv
        else:
            changed: dict[str, Any] = {}
            if existing_obj.quantity_on_hand != item.quantity_on_hand:
                changed["quantity_on_hand"] = item.quantity_on_hand
            if existing_obj.safety_stock != ss_val:
                changed["safety_stock"] = ss_val
            if existing_obj.reorder_point != stored_rop:
                changed["reorder_point"] = stored_rop

            if not changed:
                counts.unchanged += 1
            else:
                counts.updated += 1
                if not dry_run:
                    for k_name, val in changed.items():
                        setattr(existing_obj, k_name, val)

    return counts, snapshot_records


def _apply_purchase_order_history(
    db: Session,
    parsed: list[_ParsedPurchaseOrder],
    valid_sku_ids: set[str],
    valid_warehouse_ids: set[str],
    valid_supplier_ids: set[str],
    dry_run: bool,
) -> EntityImportCounts:
    for idx, item in enumerate(parsed, start=1):
        if item.sku_id not in valid_sku_ids:
            raise ClientImportValidationError(
                f"purchase_order_history[row {idx}]: unknown sku_id '{item.sku_id}' (missing foreign key in products)"
            )
        if item.warehouse_id not in valid_warehouse_ids:
            raise ClientImportValidationError(
                f"purchase_order_history[row {idx}]: unknown warehouse_id '{item.warehouse_id}' (missing foreign key in warehouses)"
            )
        if item.supplier_id not in valid_supplier_ids:
            raise ClientImportValidationError(
                f"purchase_order_history[row {idx}]: unknown supplier_id '{item.supplier_id}' (missing foreign key in suppliers)"
            )

    existing = {po.po_id: po for po in db.query(PurchaseOrder).all()}
    counts = EntityImportCounts()

    for item in parsed:
        existing_obj = existing.get(item.po_id)
        expected_cost = round(item.quantity_ordered * item.unit_cost, 2)
        norm_status = item.po_status.lower()

        if existing_obj is None:
            counts.added += 1
            if not dry_run:
                new_po = PurchaseOrder(
                    po_id=item.po_id,
                    sku_id=item.sku_id,
                    warehouse_id=item.warehouse_id,
                    supplier_id=item.supplier_id,
                    quantity=item.quantity_ordered,
                    unit_cost=item.unit_cost,
                    expected_cost=expected_cost,
                    status=norm_status,
                    approval_status="approved",  # already decided in the client's system
                    order_date=item.order_date,
                    expected_date=item.expected_date,
                    received_date=item.received_date,
                )
                db.add(new_po)
                existing[item.po_id] = new_po
        else:
            changed: dict[str, Any] = {}
            if existing_obj.sku_id != item.sku_id:
                changed["sku_id"] = item.sku_id
            if existing_obj.warehouse_id != item.warehouse_id:
                changed["warehouse_id"] = item.warehouse_id
            if existing_obj.supplier_id != item.supplier_id:
                changed["supplier_id"] = item.supplier_id
            if existing_obj.quantity != item.quantity_ordered:
                changed["quantity"] = item.quantity_ordered
            if not math.isclose(
                existing_obj.unit_cost, item.unit_cost, rel_tol=0.0, abs_tol=1e-9
            ):
                changed["unit_cost"] = item.unit_cost
            if not math.isclose(
                existing_obj.expected_cost, expected_cost, rel_tol=0.0, abs_tol=1e-9
            ):
                changed["expected_cost"] = expected_cost
            if existing_obj.status != norm_status:
                changed["status"] = norm_status
            if existing_obj.order_date != item.order_date:
                changed["order_date"] = item.order_date
            if existing_obj.expected_date != item.expected_date:
                changed["expected_date"] = item.expected_date
            if existing_obj.received_date != item.received_date:
                changed["received_date"] = item.received_date

            if not changed:
                counts.unchanged += 1
            else:
                counts.updated += 1
                if not dry_run:
                    for k_name, val in changed.items():
                        setattr(existing_obj, k_name, val)

    return counts


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
    parsed_snapshots = _parse_inventory_snapshots(dataset.inventory_snapshots)
    parsed_pos = _parse_purchase_order_history(dataset.purchase_order_history)

    valid_supplier_ids = {row[0] for row in db.query(Supplier.supplier_id).all()}
    existing_products = {row.sku_id: row for row in db.query(Product).all()}
    valid_sku_ids = set(existing_products) | {p.sku_id for p in parsed_products}
    existing_warehouses = {row.warehouse_id: row for row in db.query(Warehouse).all()}
    valid_warehouse_ids = set(existing_warehouses) | {
        w.warehouse_id for w in parsed_warehouses
    }

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
            db.flush()

        snapshot_counts, snapshot_records = _apply_inventory_snapshots(
            db,
            parsed_snapshots,
            valid_sku_ids=valid_sku_ids,
            valid_warehouse_ids=valid_warehouse_ids,
            products_by_id=existing_products,
            dry_run=dry_run,
        )
        if not dry_run:
            db.flush()

        po_counts = _apply_purchase_order_history(
            db,
            parsed_pos,
            valid_sku_ids=valid_sku_ids,
            valid_warehouse_ids=valid_warehouse_ids,
            valid_supplier_ids=valid_supplier_ids,
            dry_run=dry_run,
        )
        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise

    # Supplier performance metrics
    supplier_perf_list: list[SupplierPerformanceSummary] = []
    perf_records = calculate_all_suppliers_performance(db)
    supplier_perf_map = {p.supplier_id: p for p in perf_records}
    for p in perf_records:
        if p.total_po_count > 0:
            supplier_perf_list.append(
                SupplierPerformanceSummary(
                    supplier_id=p.supplier_id,
                    supplier_name=p.supplier_name,
                    received_po_count=p.received_po_count,
                    on_time_po_count=p.on_time_po_count,
                    on_time_delivery_percent=p.on_time_delivery_percent,
                    total_po_count=p.total_po_count,
                    open_po_count=p.open_po_count,
                    cancelled_po_count=p.cancelled_po_count,
                    late_po_count=p.late_po_count,
                    unverified_po_count=p.unverified_po_count,
                )
            )

    # Reorder recommendations evaluation
    reorder_recs: list[ReorderSummaryItem] = []
    if parsed_snapshots:
        reorder_context = build_reorder_context(db)
        inv_map = {
            (inv.sku_id, inv.warehouse_id): inv for inv in db.query(Inventory).all()
        }
        for snap_rec in snapshot_records:
            key = (snap_rec.sku_id, snap_rec.warehouse_id)
            inv_item = inv_map.get(key)
            if inv_item is not None:
                calc = calculate_reorder_point(db, inv_item, context=reorder_context)
                rop_for_eval = calc["reorder_point"]
                needs_reorder = inv_item.quantity_on_hand < rop_for_eval
                suggested_qty = (
                    max(rop_for_eval - inv_item.quantity_on_hand, 1)
                    if needs_reorder
                    else 0
                )
            else:
                needs_reorder = snap_rec.quantity_on_hand < snap_rec.reorder_point
                suggested_qty = (
                    max(snap_rec.reorder_point - snap_rec.quantity_on_hand, 1)
                    if needs_reorder
                    else 0
                )

            sup_id = ""
            sup_name = ""
            unit_cost = 0.0
            on_time_pct: float | None = None
            try:
                supplier_choice = select_supplier(db, snap_rec.sku_id)
                sup_id = supplier_choice.supplier_id
                sup_name = supplier_choice.supplier_name
                unit_cost = float(supplier_choice.unit_cost)
                if sup_id in supplier_perf_map:
                    on_time_pct = supplier_perf_map[sup_id].on_time_delivery_percent
            except ValueError as exc:
                logger.warning("No supplier for %s: %s", snap_rec.sku_id, exc)
                sup_name = "no supplier found"

            expected_spend = round(suggested_qty * unit_cost, 2)
            prod = existing_products.get(snap_rec.sku_id)
            prod_name = prod.name if prod else f"Product {snap_rec.sku_id}"

            reorder_recs.append(
                ReorderSummaryItem(
                    sku_id=snap_rec.sku_id,
                    product_name=prod_name,
                    warehouse_id=snap_rec.warehouse_id,
                    quantity_on_hand=snap_rec.quantity_on_hand,
                    reorder_point=snap_rec.reorder_point,
                    safety_stock=snap_rec.safety_stock,
                    needs_reorder=needs_reorder,
                    suggested_quantity=suggested_qty,
                    supplier_id=sup_id,
                    supplier_name=sup_name,
                    unit_cost=unit_cost,
                    expected_cost=expected_spend,
                    supplier_on_time_percent=on_time_pct,
                    reorder_point_source=snap_rec.reorder_point_source,
                    safety_stock_source=snap_rec.safety_stock_source,
                    fallback_reason=snap_rec.fallback_reason,
                )
            )

    summary = ClientImportSummary(
        dry_run=dry_run,
        products=product_counts,
        warehouses=warehouse_counts,
        supplier_lead_times=lead_time_counts,
        inventory_snapshots=snapshot_counts,
        purchase_order_history=po_counts,
        snapshot_records=snapshot_records,
        supplier_performance=supplier_perf_list,
        reorder_recommendations=reorder_recs,
    )
    logger.info(
        "Client data import (%s): products=+%d/~%d/=%d, warehouses=+%d/~%d/=%d, "
        "lead_times=+%d/~%d/=%d, snapshots=+%d/~%d/=%d, pos=+%d/~%d/=%d",
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
        summary.inventory_snapshots.added,
        summary.inventory_snapshots.updated,
        summary.inventory_snapshots.unchanged,
        summary.purchase_order_history.added,
        summary.purchase_order_history.updated,
        summary.purchase_order_history.unchanged,
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
            raise ClientImportValidationError(f"{dataset}: CSV file has no header row")
        cleaned_records: list[dict[str, str]] = []
        for row in reader:
            cleaned_row: dict[str, str] = {
                (k.strip() if isinstance(k, str) else str(k or "")): (
                    v.strip() if isinstance(v, str) else ("" if v is None else str(v))
                )
                for k, v in row.items()
            }
            cleaned_records.append(cleaned_row)
        return cleaned_records


def load_staging_dataset_from_dir(staging_dir: Path | str) -> StagingDataset:
    """Load canonical client staging CSVs from a local staging directory."""
    resolved = Path(staging_dir).resolve()
    if not resolved.is_dir():
        raise ClientImportError(f"Staging directory does not exist: {resolved}")

    prod_path = _resolve_csv_file(resolved, "products", required=False)
    wh_path = _resolve_csv_file(resolved, "warehouses", required=False)
    lt_path = _resolve_csv_file(resolved, "supplier_lead_times", required=False)
    snap_path = _resolve_csv_file(resolved, "inventory_snapshots", required=False)
    po_path = _resolve_csv_file(resolved, "purchase_order_history", required=False)

    if not any((prod_path, wh_path, lt_path, snap_path, po_path)):
        expected_files = ", ".join(
            f"{k}: {' or '.join(v)}" for k, v in STAGING_CSV_CANDIDATES.items()
        )
        raise ClientImportError(
            f"No recognizable staging CSV files found in staging directory: {resolved}. "
            f"Expected any of: {expected_files}"
        )

    return StagingDataset(
        products=_read_csv_records(prod_path, "products") if prod_path else [],
        warehouses=_read_csv_records(wh_path, "warehouses") if wh_path else [],
        supplier_lead_times=_read_csv_records(lt_path, "supplier_lead_times")
        if lt_path
        else [],
        inventory_snapshots=_read_csv_records(snap_path, "inventory_snapshots")
        if snap_path
        else [],
        purchase_order_history=_read_csv_records(po_path, "purchase_order_history")
        if po_path
        else [],
    )


def _load_table_rows(
    db: Session, table_name: str, *, required: bool
) -> list[dict[str, Any]]:
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
        products=_load_table_rows(db, STAGING_TABLES["products"], required=False),
        warehouses=_load_table_rows(db, STAGING_TABLES["warehouses"], required=False),
        supplier_lead_times=_load_table_rows(
            db, STAGING_TABLES["supplier_lead_times"], required=False
        ),
        inventory_snapshots=_load_table_rows(
            db, STAGING_TABLES["inventory_snapshots"], required=False
        ),
        purchase_order_history=_load_table_rows(
            db, STAGING_TABLES["purchase_order_history"], required=False
        ),
    )


def _db_has_staging_tables(db: Session) -> bool:
    conn = db.connection()
    inspector = inspect(conn)
    return any(inspector.has_table(name) for name in STAGING_TABLES.values())


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

    configured_dir = staging_dir or settings.CLIENT_STAGING_DIR
    session = db or SessionLocal()
    try:
        if source == "csv":
            if not configured_dir:
                raise ClientImportError(
                    "CSV staging source requested, but neither --staging-dir "
                    "nor CLIENT_STAGING_DIR was provided"
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
                    "set CLIENT_STAGING_DIR, or populate staging tables "
                    "(stg_product_master, stg_warehouse_master, stg_supplier_lead_times)."
                )

        return import_staging_dataset(session, dataset, dry_run=dry_run)
    finally:
        if db is None:
            session.close()
