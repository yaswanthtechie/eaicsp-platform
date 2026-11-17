"""Supplier on-time delivery performance service (R15 / #325).

Calculates on-time delivery percentage strictly based on Received purchase orders:
- Received POs: on_time = (received_date <= expected_date)
- on_time_delivery_percent = (on_time_received_pos / total_received_pos) * 100
- Cancelled POs and Open POs are completely excluded from the percentage denominator and numerator.
- Safe handling of divide-by-zero (0 Received POs -> 0.0%).
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.schemas.supplier_performance import SupplierPerformanceResponse

logger = logging.getLogger(__name__)

OPEN_STATUS_SET = frozenset({"open", "draft", "acknowledged", "partially_received"})
CANCELLED_STATUS_SET = frozenset({"cancelled", "canceled"})
RECEIVED_STATUS_SET = frozenset({"received"})


def calculate_all_suppliers_performance(
    db: Session,
    *,
    supplier_id: str | None = None,
) -> list[SupplierPerformanceResponse]:
    """Compute on-time delivery performance for all suppliers or a single supplier."""
    supplier_names: dict[str, str] = {
        s.supplier_id: s.supplier_name
        for s in db.query(Supplier).all()
    }

    po_query = db.query(PurchaseOrder)
    if supplier_id is not None:
        po_query = po_query.filter(PurchaseOrder.supplier_id == supplier_id)

    pos = po_query.all()

    # Track metrics per supplier_id
    total_counts: dict[str, int] = defaultdict(int)
    received_counts: dict[str, int] = defaultdict(int)
    on_time_counts: dict[str, int] = defaultdict(int)
    late_counts: dict[str, int] = defaultdict(int)
    open_counts: dict[str, int] = defaultdict(int)
    cancelled_counts: dict[str, int] = defaultdict(int)
    unverified_counts: dict[str, int] = defaultdict(int)

    all_suppliers: set[str] = set(supplier_names.keys())

    for po in pos:
        s_id = po.supplier_id
        all_suppliers.add(s_id)
        total_counts[s_id] += 1

        norm_status = (po.status or "").strip().lower()

        if norm_status in RECEIVED_STATUS_SET:
            received_counts[s_id] += 1
            if po.received_date and po.expected_date:
                if po.received_date <= po.expected_date:
                    on_time_counts[s_id] += 1
                else:
                    late_counts[s_id] += 1
            else:
                unverified_counts[s_id] += 1
        elif norm_status in OPEN_STATUS_SET:
            open_counts[s_id] += 1
        elif norm_status in CANCELLED_STATUS_SET:
            cancelled_counts[s_id] += 1
        else:
            logger.warning(
                "PO %s has unrecognised status %r; left out of on-time metrics",
                po.po_id,
                po.status,
            )
            open_counts[s_id] += 1

    results: list[SupplierPerformanceResponse] = []
    # If a specific supplier_id was requested and has neither supplier record nor POs, return empty
    if supplier_id is not None:
        if supplier_id not in all_suppliers:
            return []
        target_ids = [supplier_id]
    else:
        target_ids = sorted(all_suppliers)

    for s_id in target_ids:
        recv = received_counts[s_id]
        ontime = on_time_counts[s_id]
        verified_recv = ontime + late_counts[s_id]
        percent = (
            round((ontime / verified_recv) * 100.0, 2)
            if verified_recv > 0
            else None
        )

        results.append(
            SupplierPerformanceResponse(
                supplier_id=s_id,
                supplier_name=supplier_names.get(s_id),
                total_po_count=total_counts[s_id],
                received_po_count=recv,
                on_time_po_count=ontime,
                late_po_count=late_counts[s_id],
                open_po_count=open_counts[s_id],
                cancelled_po_count=cancelled_counts[s_id],
                unverified_po_count=unverified_counts[s_id],
                on_time_delivery_percent=percent,
            )
        )

    return results


def get_supplier_performance(
    db: Session,
    supplier_id: str,
) -> SupplierPerformanceResponse | None:
    """Retrieve performance metrics for a specific supplier by ID."""
    results = calculate_all_suppliers_performance(db, supplier_id=supplier_id)
    if not results:
        return None
    return results[0]
