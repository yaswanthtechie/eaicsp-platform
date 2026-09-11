from datetime import date, datetime

from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices


# ============================================================
# DATE HELPER
# ============================================================

def _to_date(value):
    """
    Convert supported date/datetime/string values to date.

    Supported:
        - date
        - datetime
        - ISO date string: 2026-08-10
        - ISO datetime string: 2026-08-06T10:00:00
        - ISO datetime with Z: 2026-08-06T10:00:00Z
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

        # Handle UTC Z suffix
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        parsed = datetime.fromisoformat(value)

        return parsed.date()

    raise ValueError(
        f"Unsupported date value: {value!r}"
    )


# ============================================================
# SUPPLIER STATS
# ============================================================

def get_supplier_stats(supplier_id: str):
    """
    Return operational statistics for a supplier.

    Metrics:
        - Total purchase orders
        - On-time delivery percentage
        - Average invoice cycle time

    On-time delivery is calculated only against
    fulfilled purchase orders because only fulfilled
    orders have an actual delivery outcome.

    Invoice cycle time:
        invoice_date - purchase_order.created_at
    """

    # ========================================================
    # SUPPLIER PURCHASE ORDERS
    # ========================================================

    supplier_purchase_orders = [
        po
        for po in purchase_orders.values()
        if po.get("supplier_id") == supplier_id
    ]

    # --------------------------------------------------------
    # Supplier not found
    # --------------------------------------------------------

    supplier_invoices = [
        invoice
        for invoice in invoices.values()
        if invoice.get("supplier_id") == supplier_id
   ]

    if not supplier_purchase_orders and not supplier_invoices:
        raise ValueError(
          f"Supplier '{supplier_id}' not found."
    )

    # --------------------------------------------------------
    # Total purchase orders
    # --------------------------------------------------------

    total_po_count = len(
        supplier_purchase_orders
    )

    # --------------------------------------------------------
    # Fulfilled purchase orders
    # --------------------------------------------------------

    fulfilled_purchase_orders = [
        po
        for po in supplier_purchase_orders
        if po.get("status") == "fulfilled"
    ]

    fulfilled_po_count = len(
        fulfilled_purchase_orders
    )

    # ========================================================
    # ON-TIME DELIVERY
    # ========================================================

    on_time_count = 0

    for po in fulfilled_purchase_orders:

        expected_delivery = _to_date(
            po.get("expected_delivery")
        )

        actual_delivery = _to_date(
            po.get("actual_delivery_date")
        )

        # Cannot evaluate delivery performance
        # without both dates.
        if (
            expected_delivery is None
            or actual_delivery is None
        ):
            continue

        if actual_delivery <= expected_delivery:
            on_time_count += 1

    # --------------------------------------------------------
    # On-time percentage
    # --------------------------------------------------------

    if total_po_count > 0:
        on_time_percentage = round(
            (on_time_count / total_po_count) * 100,
            2,
        )
    else:
        on_time_percentage = 0.0

    # ========================================================
    # AVERAGE INVOICE CYCLE TIME
    # ========================================================

    cycle_times = []

    for invoice in invoices.values():

        # Only invoices belonging to this supplier
        if invoice.get("supplier_id") != supplier_id:
            continue

        po_number = invoice.get(
            "po_number"
        )

        purchase_order = purchase_orders.get(
            po_number
        )

        # Invoice references an unknown PO
        if purchase_order is None:
            continue

        # ----------------------------------------------------
        # PO creation date
        # ----------------------------------------------------

        created_at = purchase_order.get(
            "created_at"
        )

        # ----------------------------------------------------
        # Invoice date
        # ----------------------------------------------------

        invoice_date = invoice.get(
            "invoice_date"
        )

        if (
            created_at is None
            or invoice_date is None
        ):
            continue

        try:

            created_date = _to_date(
                created_at
            )

            invoice_date = _to_date(
                invoice_date
            )

        except ValueError:

            # Ignore invalid date records
            # rather than breaking the entire endpoint.
            continue

        if (
            created_date is None
            or invoice_date is None
        ):
            continue

        # ----------------------------------------------------
        # Cycle time
        # ----------------------------------------------------

        cycle_days = (
            invoice_date - created_date
        ).days

        # Prevent invalid negative cycle times
        # from corrupting the KPI.
        if cycle_days >= 0:

            cycle_times.append(
                cycle_days
            )

    # --------------------------------------------------------
    # Average cycle time
    # --------------------------------------------------------

    if cycle_times:

        average_invoice_cycle_time = round(
            sum(cycle_times)
            / len(cycle_times),
            2,
        )

    else:

        average_invoice_cycle_time = 0.0

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "supplier_id": supplier_id,

        # This represents TOTAL POs.
        "po_count": total_po_count,

        "on_time_percentage": (
            on_time_percentage
        ),

        "average_invoice_cycle_time": (
            average_invoice_cycle_time
        ),
    }


# ============================================================
# SUPPLIER SCORECARD
# ============================================================

def calculate_supplier_scorecard(
    supplier_id: str,
):
    """
    Calculate the real-time supplier performance scorecard.

    Purchase Order metrics:
        - Total purchase orders
        - Fulfilled purchase orders
        - On-time purchase orders
        - Late purchase orders
        - Pending purchase orders
        - Cancelled purchase orders
        - On-time delivery percentage
        - Late delivery percentage
        - Fulfillment rate
        - Average delay days

    Invoice metrics:
        - Total invoices
        - Disputed invoices
        - Accurate invoices
        - Inaccurate invoices
        - Approved invoices
        - Rejected invoices
        - Pending invoices
        - Invoice accuracy percentage
        - Dispute rate percentage
        - Approval rate percentage
        - Average invoice cycle time

    Overall score weighting:

        On-time delivery       = 40%
        Invoice accuracy       = 40%
        Dispute performance    = 20%

    All calculations use the current in-memory
    purchase order and invoice stores.
    """

    # ========================================================
    # PURCHASE ORDERS
    # ========================================================

    supplier_pos = [
        po
        for po in purchase_orders.values()
        if po.get("supplier_id") == supplier_id
    ]

    # ========================================================
    # INVOICES
    # ========================================================

    supplier_invoices = [
        invoice
        for invoice in invoices.values()
        if invoice.get("supplier_id") == supplier_id
    ]

    # ========================================================
    # SUPPLIER EXISTENCE
    # ========================================================

    if (
        not supplier_pos
        and not supplier_invoices
    ):
        raise ValueError(
            f"Supplier '{supplier_id}' not found."
        )

    # ========================================================
    # PURCHASE ORDER STATUS COUNTS
    # ========================================================

    fulfilled_pos = [
        po
        for po in supplier_pos
        if po.get("status") == "fulfilled"
    ]

    fulfilled_po_count = len(
        fulfilled_pos
    )

    cancelled_po_count = sum(
        1
        for po in supplier_pos
        if po.get("status") == "cancelled"
    )

    # Pending means the PO is neither fulfilled nor cancelled.
    pending_po_count = (
        len(supplier_pos)
        - fulfilled_po_count
        - cancelled_po_count
    )

    # ========================================================
    # ON-TIME PURCHASE ORDERS
    # ========================================================

    on_time_po_count = 0

    for po in fulfilled_pos:

        expected_delivery = _to_date(
            po.get("expected_delivery")
        )

        actual_delivery = _to_date(
            po.get("actual_delivery_date")
        )

        if (
            expected_delivery is None
            or actual_delivery is None
        ):
            continue

        if actual_delivery <= expected_delivery:

            on_time_po_count += 1

    # ========================================================
    # LATE PURCHASE ORDERS
    # ========================================================

    # Keep the existing behavior:
    # fulfilled POs that are not counted as on-time
    # are treated as late.
    late_po_count = (
        fulfilled_po_count
        - on_time_po_count
    )

    # ========================================================
    # ON-TIME DELIVERY %
    # ========================================================

    # Preserve the existing scorecard calculation:
    # on-time POs / total supplier POs.
    if len(supplier_pos) > 0:

        on_time_percentage = round(
            (
                on_time_po_count
                / len(supplier_pos)
            )
            * 100,
            2,
        )

    else:

        on_time_percentage = 0.0

    # ========================================================
    # LATE DELIVERY %
    # ========================================================

    if fulfilled_po_count > 0:

        late_percentage = round(
            (
                late_po_count
                / fulfilled_po_count
            )
            * 100,
            2,
        )

    else:

        late_percentage = 0.0

    # ========================================================
    # FULFILLMENT RATE
    # ========================================================

    if len(supplier_pos) > 0:

        fulfillment_rate = round(
            (
                fulfilled_po_count
                / len(supplier_pos)
            )
            * 100,
            2,
        )

    else:

        fulfillment_rate = 0.0

    # ========================================================
    # AVERAGE DELAY DAYS
    # ========================================================

    delay_days = []

    for po in fulfilled_pos:

        expected_delivery = _to_date(
            po.get("expected_delivery")
        )

        actual_delivery = _to_date(
            po.get("actual_delivery_date")
        )

        if (
            expected_delivery is None
            or actual_delivery is None
        ):
            continue

        delay = (
            actual_delivery
            - expected_delivery
        ).days

        # Only actual late deliveries
        # contribute to average delay.
        if delay > 0:

            delay_days.append(
                delay
            )

    if delay_days:

        average_delay_days = round(
            sum(delay_days)
            / len(delay_days),
            2,
        )

    else:

        average_delay_days = 0.0

    # ========================================================
    # INVOICE METRICS
    # ========================================================

    total_invoice_count = len(
        supplier_invoices
    )

    # --------------------------------------------------------
    # Disputed invoices
    #
    # An invoice is considered historically disputed if
    # the dispute field is not None.
    # --------------------------------------------------------

    disputed_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("dispute") is not None
    )

    # --------------------------------------------------------
    # Accurate invoices
    #
    # Invoice never entered dispute.
    # --------------------------------------------------------

    accurate_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("dispute") is None
    )

    # --------------------------------------------------------
    # Inaccurate invoices
    #
    # Invoice required dispute/correction.
    # --------------------------------------------------------

    inaccurate_invoice_count = (
        disputed_invoice_count
    )

    # ========================================================
    # INVOICE STATUS COUNTS
    # ========================================================

    approved_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("status") == "approved"
    )

    rejected_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("status") == "rejected"
    )

    # Any invoice which is not approved or rejected
    # is considered pending.
    pending_invoice_count = (
        total_invoice_count
        - approved_invoice_count
        - rejected_invoice_count
    )

    # ========================================================
    # INVOICE PERCENTAGES
    # ========================================================

    if total_invoice_count > 0:

        dispute_rate_percentage = round(
            (
                disputed_invoice_count
                / total_invoice_count
            )
            * 100,
            2,
        )

        invoice_accuracy_percentage = round(
            (
                accurate_invoice_count
                / total_invoice_count
            )
            * 100,
            2,
        )

        approval_rate_percentage = round(
            (
                approved_invoice_count
                / total_invoice_count
            )
            * 100,
            2,
        )

    else:

        dispute_rate_percentage = 0.0

        invoice_accuracy_percentage = 0.0

        approval_rate_percentage = 0.0

    # ========================================================
    # AVERAGE INVOICE CYCLE TIME
    # ========================================================

    cycle_times = []

    for invoice in supplier_invoices:

        po_number = invoice.get(
            "po_number"
        )

        purchase_order = purchase_orders.get(
            po_number
        )

        # Invoice references an unknown PO.
        if purchase_order is None:
            continue

        created_at = purchase_order.get(
            "created_at"
        )

        invoice_date = invoice.get(
            "invoice_date"
        )

        if (
            created_at is None
            or invoice_date is None
        ):
            continue

        try:

            created_date = _to_date(
                created_at
            )

            invoice_date = _to_date(
                invoice_date
            )

        except ValueError:

            # Ignore invalid records.
            continue

        if (
            created_date is None
            or invoice_date is None
        ):
            continue

        cycle_days = (
            invoice_date - created_date
        ).days

        if cycle_days >= 0:

            cycle_times.append(
                cycle_days
            )

    if cycle_times:

        average_cycle_time_days = round(
            sum(cycle_times)
            / len(cycle_times),
            2,
        )

    else:

        average_cycle_time_days = 0.0

    # ========================================================
    # DISPUTE PERFORMANCE
    # ========================================================

    # Lower dispute rate = better performance.
    dispute_performance = round(
        100
        - dispute_rate_percentage,
        2,
    )

    # ========================================================
    # OVERALL SUPPLIER SCORE
    # ========================================================

    # 40% Delivery
    # 40% Invoice Accuracy
    # 20% Dispute Performance

    delivery_weight = 0.40
    invoice_accuracy_weight = 0.40
    dispute_weight = 0.20

    delivery_weighted_score = round(
        on_time_percentage
        * delivery_weight,
        2,
    )

    invoice_accuracy_weighted_score = round(
        invoice_accuracy_percentage
        * invoice_accuracy_weight,
        2,
    )

    dispute_weighted_score = round(
        dispute_performance
        * dispute_weight,
        2,
    )

    overall_score = round(
        delivery_weighted_score
        + invoice_accuracy_weighted_score
        + dispute_weighted_score,
        2,
    )

    # ========================================================
    # RATING
    # ========================================================

    if overall_score >= 90:

        rating = "Excellent"

    elif overall_score >= 75:

        rating = "Good"

    elif overall_score >= 60:

        rating = "Average"

    elif overall_score >= 40:

        rating = "Needs Improvement"

    else:

        rating = "Poor"

    # ========================================================
    # PERFORMANCE STATUS
    # ========================================================

    if overall_score >= 75:

        performance_status = "Healthy"

    elif overall_score >= 60:

        performance_status = "Watch"

    elif overall_score >= 40:

        performance_status = "At Risk"

    else:

        performance_status = "Critical"

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "supplier_id": supplier_id,

        "scorecard": {
            # Existing fields
            "on_time_delivery_percentage":
                on_time_percentage,

            "dispute_rate_percentage":
                dispute_rate_percentage,

            "invoice_accuracy_percentage":
                invoice_accuracy_percentage,

            "overall_score":
                overall_score,

            # New fields
            "rating":
                rating,

            "performance_status":
                performance_status,
        },

        "score_breakdown": {
            "on_time_delivery": {
                "score":
                    on_time_percentage,

                "weight_percentage":
                    40.0,

                "weighted_score":
                    delivery_weighted_score,
            },

            "invoice_accuracy": {
                "score":
                    invoice_accuracy_percentage,

                "weight_percentage":
                    40.0,

                "weighted_score":
                    invoice_accuracy_weighted_score,
            },

            "dispute_performance": {
                "score":
                    dispute_performance,

                "weight_percentage":
                    20.0,

                "weighted_score":
                    dispute_weighted_score,
            },
        },

        "details": {
            "purchase_orders": {
                # Existing fields
                "total":
                    len(supplier_pos),

                "fulfilled":
                    fulfilled_po_count,

                "on_time":
                    on_time_po_count,

                "late":
                    late_po_count,

                # New fields
                "pending":
                    pending_po_count,

                "cancelled":
                    cancelled_po_count,

                "on_time_percentage":
                    on_time_percentage,

                "late_percentage":
                    late_percentage,

                "fulfillment_rate":
                    fulfillment_rate,

                "average_delay_days":
                    average_delay_days,
            },

            "invoices": {
                # Existing fields
                "total":
                    total_invoice_count,

                "disputed":
                    disputed_invoice_count,

                "accurate":
                    accurate_invoice_count,

                "inaccurate":
                    inaccurate_invoice_count,

                # New fields
                "approved":
                    approved_invoice_count,

                "rejected":
                    rejected_invoice_count,

                "pending":
                    pending_invoice_count,

                "accuracy_percentage":
                    invoice_accuracy_percentage,

                "dispute_rate_percentage":
                    dispute_rate_percentage,

                "approval_rate_percentage":
                    approval_rate_percentage,

                "average_cycle_time_days":
                    average_cycle_time_days,
            },
        },
    }