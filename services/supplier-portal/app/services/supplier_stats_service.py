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

    if not supplier_purchase_orders:
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
        - On-time delivery percentage

    Invoice metrics:
        - Total invoices
        - Disputed invoices
        - Accurate invoices
        - Inaccurate invoices
        - Dispute rate
        - Invoice accuracy

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
    # FULFILLED PURCHASE ORDERS
    # ========================================================

    fulfilled_pos = [
        po
        for po in supplier_pos
        if po.get("status") == "fulfilled"
    ]

    fulfilled_po_count = len(
        fulfilled_pos
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

    late_po_count = (
        fulfilled_po_count
        - on_time_po_count
    )

    # ========================================================
    # ON-TIME DELIVERY %
    # ========================================================

    if len(supplier_pos) > 0:
      on_time_percentage = round(
        (on_time_po_count / len(supplier_pos)) * 100,
        2,
    )
    else:
      on_time_percentage = 0.0

    # ========================================================
    # INVOICE METRICS
    # ========================================================

    total_invoice_count = len(
        supplier_invoices
    )

    # --------------------------------------------------------
    # Disputed invoices
    #
    # IMPORTANT:
    #
    # dispute != None means the invoice
    # entered the dispute process at least once.
    #
    # Even if later approved, it remains historically
    # disputed for supplier accuracy measurement.
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

    else:

        dispute_rate_percentage = 0.0

        invoice_accuracy_percentage = 0.0

    # ========================================================
    # DISPUTE PERFORMANCE
    # ========================================================

    dispute_performance = round(
        100
        - dispute_rate_percentage,
        2,
    )

    # ========================================================
    # OVERALL SUPPLIER SCORE
    # ========================================================

    overall_score = round(
        (
            on_time_percentage * 0.40
            + invoice_accuracy_percentage * 0.40
            + dispute_performance * 0.20
        ),
        2,
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "supplier_id": supplier_id,

        "scorecard": {
            "on_time_delivery_percentage":
                on_time_percentage,

            "dispute_rate_percentage":
                dispute_rate_percentage,

            "invoice_accuracy_percentage":
                invoice_accuracy_percentage,

            "overall_score":
                overall_score,
        },

        "details": {
            "purchase_orders": {
                "total":
                    len(supplier_pos),

                "fulfilled":
                    fulfilled_po_count,

                "on_time":
                    on_time_po_count,

                "late":
                    late_po_count,
            },

            "invoices": {
                "total":
                    total_invoice_count,

                "disputed":
                    disputed_invoice_count,

                "accurate":
                    accurate_invoice_count,

                "inaccurate":
                    inaccurate_invoice_count,
            },
        },
    }