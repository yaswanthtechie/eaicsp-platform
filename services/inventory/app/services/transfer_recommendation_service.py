import logging
import math
from collections import defaultdict
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.outbox import Outbox
from app.models.product import Product
from app.models.supplier import Supplier
from app.schemas.events import InventoryTransferRecommendedPayload
from app.services.outbox_service import record_event
from app.services.reorder_service import (
    build_reorder_context,
    calculate_reorder_point,
)

logger = logging.getLogger(__name__)


def find_configured_lane(
    from_warehouse: str,
    to_warehouse: str,
    lanes: Optional[list[dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    """Look up a configured transfer lane between two warehouses."""
    configured_lanes = lanes if lanes is not None else settings.TRANSFER_LANES

    for lane in configured_lanes:
        f = lane.get("from_warehouse") or lane.get("from")
        t = lane.get("to_warehouse") or lane.get("to")
        if f == from_warehouse and t == to_warehouse:
            return {
                "from_warehouse": f,
                "to_warehouse": t,
                "lead_time_days": int(lane.get("lead_time_days", 0)),
                "cost_per_unit": float(lane.get("cost_per_unit", 0.0)),
            }
    return None


def get_sku_unit_cost(db: Session, sku_id: str) -> float:
    """Retrieve SKU unit cost from Supplier, Product, or fallback default."""
    supplier = db.query(Supplier).filter(Supplier.sku_id == sku_id).first()
    if supplier and supplier.unit_cost is not None and supplier.unit_cost > 0:
        return float(supplier.unit_cost)

    product = db.query(Product).filter(Product.sku_id == sku_id).first()
    if product and product.unit_cost is not None and product.unit_cost > 0:
        return float(product.unit_cost)

    return float(settings.TRANSFER_DEFAULT_UNIT_COST)


def calculate_stock_cover(
    quantity_on_hand: int,
    avg_daily_demand: float,
) -> tuple[float, bool, int]:
    """
    Calculate stock cover days, excess flag, and reserve units required.

    Returns:
        tuple[float, bool, int]: (stock_cover_days, has_excess, cover_reserve_units)
    """
    threshold_days = settings.TRANSFER_EXCESS_STOCK_COVER_DAYS

    if avg_daily_demand > 0:
        cover_days = round(quantity_on_hand / avg_daily_demand, 2)
        has_excess = cover_days > threshold_days
        reserve_units = math.ceil(avg_daily_demand * threshold_days)
    else:
        # 0 demand with positive stock has infinite cover (dormant/excess stock)
        cover_days = float("inf") if quantity_on_hand > 0 else 0.0
        has_excess = quantity_on_hand > 0
        reserve_units = 0

    return cover_days, has_excess, reserve_units


def generate_transfer_recommendations(
    db: Session,
    publish_events: bool = False,
) -> list[dict[str, Any]]:
    """
    Evaluate all inventory items below reorder point and recommend either an
    inter-warehouse transfer or a standard purchase order.

    Rules:
    1. Only destination warehouses where quantity_on_hand < reorder_point are evaluated.
    2. Candidate source warehouses must hold the same SKU, have stock cover above
       TRANSFER_EXCESS_STOCK_COVER_DAYS, and have a configured transfer lane.
    3. Never take the source warehouse below its own reorder point.
    4. Recommend transfer when transfer_lead_time < po_lead_time AND
       transfer_cost < TRANSFER_MAX_PO_COST_SHARE * po_cost.
    5. When a transfer is recommended and publish_events=True, emit
       inventory.transfer.recommended event via transactional outbox.
    """
    context = build_reorder_context(db=db)
    all_inventories = db.query(Inventory).all()

    # Units already promised from each (sku, source warehouse) in this run,
    # so two destinations cannot both take the same spare stock.
    allocated: dict[tuple[str, str], int] = defaultdict(int)
    pending_events: list[dict[str, Any]] = []

    recommendations: list[dict[str, Any]] = []

    for dest in all_inventories:
        dest_calc = calculate_reorder_point(
            db=db,
            inventory=dest,
            context=context,
        )
        dest_rop = int(dest_calc["reorder_point"])

        # Rule 1: Only evaluate if below reorder point
        if dest.quantity_on_hand >= dest_rop:
            continue

        shortage = dest_rop - int(dest.quantity_on_hand)
        if shortage <= 0:
            continue

        # PO baseline values
        po_lead_time_days = (
            int(dest.lead_time_days)
            if dest.lead_time_days is not None
            else settings.TRANSFER_DEFAULT_PO_LEAD_TIME_DAYS
        )
        po_unit_cost = get_sku_unit_cost(db=db, sku_id=dest.sku_id)

        # Find potential source warehouses for the same SKU
        other_warehouses = [
            inv
            for inv in all_inventories
            if inv.sku_id == dest.sku_id and inv.warehouse_id != dest.warehouse_id
        ]

        viable_candidates: list[dict[str, Any]] = []
        disqualification_reasons: list[str] = []

        if not other_warehouses:
            disqualification_reasons.append(
                "no other warehouse holds stock for this SKU"
            )

        for source in other_warehouses:
            lane = find_configured_lane(
                from_warehouse=source.warehouse_id,
                to_warehouse=dest.warehouse_id,
            )

            if not lane:
                disqualification_reasons.append(
                    f"no configured transfer lane from {source.warehouse_id}"
                )
                continue

            source_calc = calculate_reorder_point(
                db=db,
                inventory=source,
                context=context,
            )
            source_rop = int(source_calc["reorder_point"])
            source_avg_demand = float(source_calc["rolling_avg_demand"])

            cover_days, has_excess, cover_reserve = calculate_stock_cover(
                quantity_on_hand=int(source.quantity_on_hand),
                avg_daily_demand=source_avg_demand,
            )

            if not has_excess:
                disqualification_reasons.append(
                    f"{source.warehouse_id} stock cover ({cover_days}d) does not exceed {settings.TRANSFER_EXCESS_STOCK_COVER_DAYS}d"
                )
                continue

            # Protect source warehouse: never take below its own reorder point or required cover
            source_min_required = max(source_rop, cover_reserve)
            already_allocated = allocated[(source.sku_id, source.warehouse_id)]
            source_excess = max(
                0,
                int(source.quantity_on_hand) - already_allocated - source_min_required,
            )

            if source_excess <= 0:
                disqualification_reasons.append(
                    f"{source.warehouse_id} has no excess stock above reorder point ({source_rop})"
                )
                continue

            transfer_qty = min(shortage, source_excess)
            if transfer_qty <= 0:
                continue

            transfer_lt = lane["lead_time_days"]
            transfer_cost = round(transfer_qty * lane["cost_per_unit"], 2)
            po_cost_for_qty = round(transfer_qty * po_unit_cost, 2)
            max_allowed_cost = round(
                settings.TRANSFER_MAX_PO_COST_SHARE * po_cost_for_qty, 2
            )

            is_faster = transfer_lt < po_lead_time_days
            is_cheaper = transfer_cost < max_allowed_cost

            if not is_faster:
                disqualification_reasons.append(
                    f"lane from {source.warehouse_id} ({transfer_lt}d) is not faster than PO ({po_lead_time_days}d)"
                )
                continue

            if not is_cheaper:
                disqualification_reasons.append(
                    f"transfer cost from {source.warehouse_id} ({transfer_cost}) is not less than {settings.TRANSFER_MAX_PO_COST_SHARE * 100:.0f}% of PO cost ({max_allowed_cost})"
                )
                continue

            days_saved = po_lead_time_days - transfer_lt
            cost_savings = round(po_cost_for_qty - transfer_cost, 2)

            viable_candidates.append(
                {
                    "source": source,
                    "lane": lane,
                    "transfer_quantity": transfer_qty,
                    "source_excess": source_excess,
                    "source_rop": source_rop,
                    "source_stock_cover": cover_days,
                    "transfer_lead_time": transfer_lt,
                    "transfer_cost": transfer_cost,
                    "po_cost_for_qty": po_cost_for_qty,
                    "days_saved": days_saved,
                    "cost_savings": cost_savings,
                    "cost_share_ratio": round(transfer_cost / po_cost_for_qty, 4)
                    if po_cost_for_qty > 0
                    else 0.0,
                }
            )

        if viable_candidates:
            # Sort: highest days saved, lowest transfer cost, highest source excess
            viable_candidates.sort(
                key=lambda c: (
                    -c["days_saved"],
                    c["transfer_cost"],
                    -c["source_excess"],
                )
            )
            best = viable_candidates[0]
            best_source = best["source"]
            best_lane = best["lane"]
            transfer_qty = best["transfer_quantity"]
            transfer_cost = best["transfer_cost"]
            days_saved = best["days_saved"]
            cost_savings = best["cost_savings"]

            allocated[(best_source.sku_id, best_source.warehouse_id)] += best[
                "transfer_quantity"
            ]

            reason = (
                f"Transfer from {best_source.warehouse_id} arrives {days_saved} days faster "
                f"than PO ({best['transfer_lead_time']} vs {po_lead_time_days} days) and "
                f"costs {transfer_cost:.2f} (< {settings.TRANSFER_MAX_PO_COST_SHARE * 100:.0f}% of PO cost {best['po_cost_for_qty']:.2f})"
            )

            rec_entry = {
                "sku_id": dest.sku_id,
                "product_name": dest.product_name,
                "destination_warehouse_id": dest.warehouse_id,
                "recommendation": "TRANSFER",
                "reason": reason,
                "source_warehouse_id": best_source.warehouse_id,
                "recommended_quantity": transfer_qty,
                "days_saved": days_saved,
                "estimated_cost_savings": cost_savings,
                "numbers": {
                    "destination_quantity_on_hand": int(dest.quantity_on_hand),
                    "destination_reorder_point": dest_rop,
                    "shortage_quantity": shortage,
                    "recommended_quantity": transfer_qty,
                    "po_lead_time_days": po_lead_time_days,
                    "po_unit_cost": po_unit_cost,
                    "po_cost": best["po_cost_for_qty"],
                    "source_warehouse_id": best_source.warehouse_id,
                    "source_quantity_on_hand": int(best_source.quantity_on_hand),
                    "source_reorder_point": best["source_rop"],
                    "source_stock_cover_days": None
                    if math.isinf(best["source_stock_cover"])
                    else best["source_stock_cover"],
                    "source_excess_quantity": best["source_excess"],
                    "transfer_lead_time_days": best["transfer_lead_time"],
                    "transfer_cost_per_unit": best_lane["cost_per_unit"],
                    "transfer_cost": transfer_cost,
                    "cost_share_ratio": best["cost_share_ratio"],
                    "max_allowed_cost_share": settings.TRANSFER_MAX_PO_COST_SHARE,
                    "min_stock_cover_days": float(
                        settings.TRANSFER_EXCESS_STOCK_COVER_DAYS
                    ),
                },
            }

            pending_events.append(
                {
                    "sku_id": dest.sku_id,
                    "source_warehouse_id": best_source.warehouse_id,
                    "destination_warehouse_id": dest.warehouse_id,
                    "transfer_quantity": transfer_qty,
                    "transfer_lead_time_days": best["transfer_lead_time"],
                    "transfer_cost": transfer_cost,
                    "po_lead_time_days": po_lead_time_days,
                    "po_cost": best["po_cost_for_qty"],
                    "cost_savings": cost_savings,
                    "reason": reason,
                }
            )

            recommendations.append(rec_entry)

            remaining = shortage - transfer_qty
            if remaining > 0:
                recommendations.append(
                    _purchase_order_entry(
                        dest=dest,
                        quantity=remaining,
                        dest_rop=dest_rop,
                        shortage=shortage,
                        po_lead_time_days=po_lead_time_days,
                        po_unit_cost=po_unit_cost,
                        reason=(
                            f"PO recommended for the remaining {remaining} units: "
                            f"transfer from {best_source.warehouse_id} covers "
                            f"{transfer_qty} of {shortage}"
                        ),
                    )
                )

        else:
            # Fallback to PO recommendation as today
            reason_detail = (
                "; ".join(disqualification_reasons)
                if disqualification_reasons
                else "no candidate warehouse available"
            )
            recommendations.append(
                _purchase_order_entry(
                    dest=dest,
                    quantity=shortage,
                    dest_rop=dest_rop,
                    shortage=shortage,
                    po_lead_time_days=po_lead_time_days,
                    po_unit_cost=po_unit_cost,
                    reason=f"PO recommended: {reason_detail}",
                )
            )

    if publish_events:
        published = _publish_transfer_events(db, pending_events)
        logger.info(
            "transfer recommendations: %d rows, %d new events",
            len(recommendations),
            published,
        )

    return recommendations


def _purchase_order_entry(
    dest: Inventory,
    quantity: int,
    dest_rop: int,
    shortage: int,
    po_lead_time_days: int,
    po_unit_cost: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "sku_id": dest.sku_id,
        "product_name": dest.product_name,
        "destination_warehouse_id": dest.warehouse_id,
        "recommendation": "PURCHASE_ORDER",
        "reason": reason,
        "source_warehouse_id": None,
        "recommended_quantity": quantity,
        "days_saved": 0,
        "estimated_cost_savings": 0.0,
        "numbers": {
            "destination_quantity_on_hand": int(dest.quantity_on_hand),
            "destination_reorder_point": dest_rop,
            "shortage_quantity": shortage,
            "recommended_quantity": quantity,
            "po_lead_time_days": po_lead_time_days,
            "po_unit_cost": po_unit_cost,
            "po_cost": round(quantity * po_unit_cost, 2),
            "source_warehouse_id": None,
            "source_quantity_on_hand": None,
            "source_reorder_point": None,
            "source_stock_cover_days": None,
            "source_excess_quantity": None,
            "transfer_lead_time_days": None,
            "transfer_cost_per_unit": None,
            "transfer_cost": None,
            "cost_share_ratio": None,
            "max_allowed_cost_share": settings.TRANSFER_MAX_PO_COST_SHARE,
            "min_stock_cover_days": float(settings.TRANSFER_EXCESS_STOCK_COVER_DAYS),
        },
    }


def _publish_transfer_events(db: Session, events: list[dict[str, Any]]) -> int:
    """Record each transfer event once per day, then commit once."""
    published = 0
    today = date.today().strftime("%Y%m%d")
    for payload in events:
        payload = InventoryTransferRecommendedPayload(**payload).model_dump()
        aggregate_id = (
            f"TRF-{payload['sku_id']}-{payload['source_warehouse_id']}-"
            f"{payload['destination_warehouse_id']}-{today}"
        )
        already = (
            db.query(Outbox.id)
            .filter(
                Outbox.event_type == "inventory.transfer.recommended",
                Outbox.aggregate_id == aggregate_id,
            )
            .first()
        )
        if already:
            continue
        record_event(
            db=db,
            event_type="inventory.transfer.recommended",
            aggregate_type="transfer_recommendation",
            aggregate_id=aggregate_id,
            payload=payload,
        )
        published += 1
    db.commit()
    return published
