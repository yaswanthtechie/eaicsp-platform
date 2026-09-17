from datetime import date, datetime 
 
from app.services.purchase_order_service import purchase_orders 
from app.services.invoice_service import invoices 
from app.services.goods_receipt_service import goods_receipts 
 
 
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
 
        # Handle UTC Z suffix. 
        if value.endswith("Z"): 
            value = value[:-1] + "+00:00" 
 
        parsed = datetime.fromisoformat(value) 
 
        return parsed.date() 
 
    raise ValueError( 
        f"Unsupported date value: {value!r}" 
    ) 
 
def _is_delivery_eligible(po):
    """
    Determine whether a purchase order should be included
    in delivery-performance calculations.

    Eligible:
        - Fulfilled POs
        - Unfulfilled POs whose expected delivery date has passed

    Not eligible:
        - Future-due unfulfilled POs
        - Cancelled POs
        - POs without an expected delivery date
    """

    if po.get("status") == "cancelled":
        return False

    if po.get("status") == "fulfilled":
        return True

    expected_delivery = _to_date(
        po.get("expected_delivery")
    )

    if expected_delivery is None:
        return False

    return expected_delivery < date.today()
 
# ============================================================ 
# INVOICE / PO HELPER 
# ============================================================ 
 
def _get_invoice_po_numbers(invoice): 
    """ 
    Return the unique purchase-order numbers referenced 
    by an invoice's line items. 
 
    Real invoices store PO numbers inside: 
 
        invoice["items"][*]["po_number"] 
 
    Example: 
 
        { 
            "invoice_number": "INV001", 
            "supplier_id": "SUP001", 
            "items": [ 
                { 
                    "po_number": "PO1001", 
                    "item_code": "LAP001", 
                    ... 
                } 
            ] 
        } 
 
    A backward-compatible fallback for the older in-memory 
    test shape with a top-level "po_number" is retained. 
    """ 
 
    po_numbers = [] 
 
    for item in invoice.get("items", []): 
 
        if not isinstance(item, dict): 
            continue 
 
        po_number = item.get("po_number") 
 
        if ( 
            po_number 
            and po_number not in po_numbers 
        ): 
            po_numbers.append( 
                po_number 
            ) 
 
    # Backward-compatible fallback for older 
    # test fixtures. 
    if not po_numbers: 
 
        po_number = invoice.get( 
            "po_number" 
        ) 
 
        if po_number: 
            po_numbers.append( 
                po_number 
            ) 
 
    return po_numbers 
 
 
# ============================================================ 
# SUPPLIER STATS 
# ============================================================ 
def get_supplier_stats(supplier_id):
  # Use the common delivery-eligibility rule so that
  # supplier stats, scorecard, and monthly trend calculations
   # remain consistent.
    supplier_pos = [
        po
        for po in purchase_orders.values()
        if po.get("supplier_id") == supplier_id
    ]

    supplier_invoices = [
        invoice
        for invoice in invoices.values()
        if invoice.get("supplier_id") == supplier_id
    ]

    if not supplier_pos and not supplier_invoices:
        raise ValueError(
            f"Supplier '{supplier_id}' not found."
    )

    # ---------------------------------------------------------
    # Purchase Order statistics
    # ---------------------------------------------------------

    po_count = len(supplier_pos)

    # The /stats endpoint historically measures delivery performance
    # using fulfilled POs only.
    #
    # Do not use _is_delivery_eligible() here because that helper is
    # intentionally stricter and is used by the scorecard to count
    # past-due unfulfilled POs as delivery misses.
    eligible_delivery_pos = [
        po
        for po in supplier_pos
        if _is_delivery_eligible(po)
    ]

    on_time_count = 0

    for po in eligible_delivery_pos:
        try:
            expected_delivery = _to_date(
                po.get("expected_delivery")
            )
            actual_delivery = _to_date(
                po.get("actual_delivery_date")
            )
        except (TypeError, ValueError):
            continue

        if (
            actual_delivery is not None
            and expected_delivery is not None
            and actual_delivery <= expected_delivery
        ):
            on_time_count += 1

    if eligible_delivery_pos:
        on_time_percentage = round(
            (on_time_count / len(eligible_delivery_pos)) * 100,
            2,
        )
    else:
        on_time_percentage = 0.0

    # ---------------------------------------------------------
    # Invoice cycle time
    # ---------------------------------------------------------

    invoice_cycle_times = []

    for invoice in supplier_invoices:
        try:
            invoice_date = _to_date(
                invoice.get("invoice_date")
            )
        except (TypeError, ValueError):
            continue

        if invoice_date is None:
            continue

        for po_number in _get_invoice_po_numbers(invoice):
            po = purchase_orders.get(po_number)

            if not po:
                continue

            if po.get("supplier_id") != supplier_id:
                continue

            try:
                created_date = _to_date(
                    po.get("created_at")
                )
            except (TypeError, ValueError):
                continue

            if created_date is None:
                continue

            cycle_time = (
                invoice_date - created_date
            ).days

            if cycle_time >= 0:
                invoice_cycle_times.append(cycle_time)

    if invoice_cycle_times:
        average_invoice_cycle_time = round(
            sum(invoice_cycle_times)
            / len(invoice_cycle_times),
            2,
        )
    else:
        average_invoice_cycle_time = 0.0

    return {
        "supplier_id": supplier_id,
        "po_count": po_count,
        "on_time_percentage": on_time_percentage,
        "invoice_count": len(supplier_invoices),
        "average_invoice_cycle_time": average_invoice_cycle_time,
        
    }
 
 
# ============================================================ 
# MILESTONE 4 - AVERAGE FULFILLMENT TIME 
# ============================================================ 
 
def _calculate_average_fulfillment_time( 
    supplier_pos, 
): 
    """ 
    Calculate average supplier fulfillment time. 
 
    Fulfillment time: 
        PO created_at -> Goods Receipt receipt_date 
 
    Only POs having both dates are included. 
    Invalid or negative durations are ignored. 
    """ 
 
    fulfillment_times = [] 
 
    for po in supplier_pos: 
 
        po_number = po.get("po_number") 
 
        created_at = po.get( 
            "created_at" 
        ) 
 
        if ( 
            po_number is None 
            or created_at is None 
        ): 
            continue 
 
        try: 
 
            created_date = _to_date( 
                created_at 
            ) 
 
        except ValueError: 
 
            continue 
 
        if created_date is None: 
            continue 
 
        # ---------------------------------------------------- 
        # Find goods receipt for this PO 
        # ---------------------------------------------------- 
 
        po_receipts = [ 
            receipt 
            for receipt in goods_receipts.values() 
            if ( 
                receipt.get("po_number") 
                == po_number 
                and receipt.get("supplier_id") 
                == po.get("supplier_id") 
            ) 
        ] 
 
        if not po_receipts: 
            continue 
 
        # A PO should normally have one goods receipt. 
        # If multiple receipts exist, use the earliest 
        # receipt date as the fulfillment completion date. 
        receipt_dates = [] 
 
        for receipt in po_receipts: 
 
            receipt_date = receipt.get( 
                "receipt_date" 
            ) 
 
            if receipt_date is None: 
                continue 
 
            try: 
 
                receipt_date = _to_date( 
                    receipt_date 
                ) 
 
            except ValueError: 
 
                continue 
 
            if receipt_date is not None: 
 
                receipt_dates.append( 
                    receipt_date 
                ) 
 
        if not receipt_dates: 
            continue 
 
        fulfillment_date = min( 
            receipt_dates 
        ) 
 
        fulfillment_days = ( 
            fulfillment_date - created_date 
        ).days 
 
        # Ignore invalid negative durations. 
        if fulfillment_days >= 0: 
 
            fulfillment_times.append( 
                fulfillment_days 
            ) 
 
    if fulfillment_times: 
 
        return round( 
            sum(fulfillment_times) 
            / len(fulfillment_times), 
            2, 
        ) 
 
    return 0.0 
 
 # ============================================================
# MILESTONE 4 - SUPPLIER PERFORMANCE TREND
# ============================================================

def _calculate_supplier_trend(
    supplier_id: str,
    supplier_pos,
    supplier_invoices,
):
    """
    Calculate monthly supplier performance trend.

    Trend period:
        PO creation month (YYYY-MM)

    Metrics:
        - On-time delivery percentage
        - Invoice dispute rate
        - Invoice accuracy percentage
        - Average fulfillment time

    Monthly delivery eligibility is consistent with the
    overall supplier performance rules:

        - Fulfilled POs are eligible.
        - Past-due unfulfilled POs are eligible and count
          as delivery misses.
        - Future-due unfulfilled POs are excluded.
        - Cancelled POs are excluded.

    Monthly on-time percentage is calculated as:

        on-time eligible POs / all eligible POs

    Invoice records are associated with their PO
    creation month using the PO number stored inside
    invoice line items.
    """

    # --------------------------------------------------------
    # Group supplier POs by creation month
    # --------------------------------------------------------

    monthly_pos = {}

    for po in supplier_pos:

        created_at = po.get(
            "created_at"
        )

        if created_at is None:
            continue

        try:
            created_date = _to_date(
                created_at
            )
        except ValueError:
            continue

        if created_date is None:
            continue

        period = created_date.strftime(
            "%Y-%m"
        )

        monthly_pos.setdefault(
            period,
            []
        ).append(po)

    # --------------------------------------------------------
    # Group invoices by the month of their
    # associated PO creation date.
    # --------------------------------------------------------

    monthly_invoices = {}

    for invoice in supplier_invoices:

        po_numbers = _get_invoice_po_numbers(
            invoice
        )

        if not po_numbers:
            continue

        # An invoice may reference multiple POs.
        # Associate it with each PO creation month.
        invoice_periods = set()

        for po_number in po_numbers:

            purchase_order = purchase_orders.get(
                po_number
            )

            if purchase_order is None:
                continue

            created_at = purchase_order.get(
                "created_at"
            )

            if created_at is None:
                continue

            try:
                created_date = _to_date(
                    created_at
                )
            except ValueError:
                continue

            if created_date is None:
                continue

            period = created_date.strftime(
                "%Y-%m"
            )

            invoice_periods.add(
                period
            )

        for period in invoice_periods:

            monthly_invoices.setdefault(
                period,
                []
            ).append(invoice)

    # --------------------------------------------------------
    # Include months appearing in either POs or invoices.
    # --------------------------------------------------------

    periods = sorted(
        set(monthly_pos.keys())
        | set(monthly_invoices.keys())
    )

    trend = []

    for period in periods:

        period_pos = monthly_pos.get(
            period,
            []
        )

        period_invoices = monthly_invoices.get(
            period,
            []
        )

        # ====================================================
        # MONTHLY ON-TIME DELIVERY
        # ====================================================

        # Use the same eligibility rule as the overall
        # supplier stats and scorecard calculations.
        eligible_delivery_pos = [
            po
            for po in period_pos
            if _is_delivery_eligible(po)
        ]

        on_time_count = 0

        for po in eligible_delivery_pos:

            expected_delivery = _to_date(
                po.get("expected_delivery")
            )

            actual_delivery = _to_date(
                po.get("actual_delivery_date")
            )

            # A missing actual delivery date means the
            # eligible PO is not on time.
            if (
                expected_delivery is None
                or actual_delivery is None
            ):
                continue

            if actual_delivery <= expected_delivery:
                on_time_count += 1

        # ----------------------------------------------------
        # Monthly trend denominator:
        #
        # on-time eligible POs / all eligible POs
        #
        # This means a past-due unfulfilled PO is counted
        # as a miss, while a future-due PO is excluded.
        # ----------------------------------------------------

        if eligible_delivery_pos:

            on_time_percentage = round(
                (
                    on_time_count
                    / len(eligible_delivery_pos)
                )
                * 100,
                2,
            )

        else:

            on_time_percentage = 0.0

        # ====================================================
        # MONTHLY INVOICE METRICS
        # ====================================================

        total_invoice_count = len(
            period_invoices
        )

        disputed_invoice_count = sum(
            1
            for invoice in period_invoices
            if invoice.get("dispute") is not None
        )

        accurate_invoice_count = sum(
            1
            for invoice in period_invoices
            if invoice.get("dispute") is None
        )

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

        # ====================================================
        # MONTHLY FULFILLMENT TIME
        # ====================================================

        average_fulfillment_time_days = (
            _calculate_average_fulfillment_time(
                period_pos
            )
        )

        # ====================================================
        # MONTHLY TREND RECORD
        # ====================================================

        trend.append(
            {
                "period": period,

                "on_time_percentage":
                    on_time_percentage,

                "dispute_rate_percentage":
                    dispute_rate_percentage,

                "invoice_accuracy_percentage":
                    invoice_accuracy_percentage,

                "average_fulfillment_time_days":
                    average_fulfillment_time_days,
            }
        )

    return trend
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
        - Average fulfillment time

    Delivery-performance eligibility:
        - Fulfilled POs are eligible.
        - Past-due unfulfilled POs are eligible and count
          as delivery misses.
        - Future-due unfulfilled POs are excluded.
        - Cancelled POs are excluded.

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
    purchase order, invoice and goods receipt stores.
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
    # DELIVERY-PERFORMANCE ELIGIBILITY
    # ========================================================

    # Delivery metrics use the common eligibility rule:
    #
    #   1. Fulfilled POs                 -> eligible
    #   2. Past-due unfulfilled POs      -> eligible
    #   3. Future-due unfulfilled POs    -> excluded
    #   4. Cancelled POs                 -> excluded
    #
    # This keeps the scorecard consistent with supplier stats
    # and supplier performance trend calculations.

    eligible_delivery_pos = [
        po
        for po in supplier_pos
        if _is_delivery_eligible(po)
    ]

    # ========================================================
    # ON-TIME PURCHASE ORDERS
    # ========================================================

    on_time_po_count = 0

    for po in eligible_delivery_pos:

        expected_delivery = _to_date(
            po.get("expected_delivery")
        )

        actual_delivery = _to_date(
            po.get("actual_delivery_date")
        )

        # An eligible PO without an actual delivery date
        # cannot be considered on-time.
        #
        # This is important for past-due unfulfilled POs:
        #
        # expected_delivery = old date
        # actual_delivery   = None
        #
        # Therefore the PO remains a delivery miss.

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

    # Every eligible delivery PO that is not on-time
    # is considered late/missed.
    #
    # This includes:
    #   - actually late fulfilled POs
    #   - past-due unfulfilled POs

    late_po_count = (
        len(eligible_delivery_pos)
        - on_time_po_count
    )

    # ========================================================
    # ON-TIME DELIVERY %
    # ========================================================

    if eligible_delivery_pos:

        on_time_percentage = round(
            (
                on_time_po_count
                / len(eligible_delivery_pos)
            )
            * 100,
            2,
        )

    else:

        on_time_percentage = 0.0

    # ========================================================
    # LATE DELIVERY %
    # ========================================================

    if eligible_delivery_pos:

        late_percentage = round(
            (
                late_po_count
                / len(eligible_delivery_pos)
            )
            * 100,
            2,
        )

    else:

        late_percentage = 0.0

    # ========================================================
    # FULFILLMENT RATE
    # ========================================================

    # IMPORTANT:
    #
    # Fulfillment rate is NOT changed to use
    # eligible_delivery_pos.
    #
    # It measures how many supplier POs were actually
    # completed out of all supplier POs.

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

        # Only actual late deliveries contribute
        # to average delay.
        #
        # Past-due unfulfilled POs are not included here
        # because they do not yet have an actual delivery date.

        if delay > 0:
            delay_days.append(delay)

    if delay_days:

        average_delay_days = round(
            sum(delay_days)
            / len(delay_days),
            2,
        )

    else:

        average_delay_days = 0.0

    # ========================================================
    # AVERAGE FULFILLMENT TIME
    # ========================================================

    average_fulfillment_time_days = (
        _calculate_average_fulfillment_time(
            supplier_pos
        )
    )

    # ========================================================
    # INVOICE METRICS
    # ========================================================

    total_invoice_count = len(
        supplier_invoices
    )

    # --------------------------------------------------------
    # Disputed invoices
    # --------------------------------------------------------

    disputed_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("dispute") is not None
    )

    # --------------------------------------------------------
    # Accurate invoices
    # --------------------------------------------------------

    accurate_invoice_count = sum(
        1
        for invoice in supplier_invoices
        if invoice.get("dispute") is None
    )

    # --------------------------------------------------------
    # Inaccurate invoices
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

    # Any invoice that is not approved or rejected
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

        # Real invoice schema stores PO numbers inside
        # invoice line items.

        po_numbers = _get_invoice_po_numbers(
            invoice
        )

        if not po_numbers:
            continue

        # ----------------------------------------------------
        # Calculate cycle time for every referenced PO.
        # ----------------------------------------------------

        for po_number in po_numbers:

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

                invoice_date_value = _to_date(
                    invoice_date
                )

            except ValueError:

                # Ignore invalid date records.
                continue

            if (
                created_date is None
                or invoice_date_value is None
            ):
                continue

            cycle_days = (
                invoice_date_value
                - created_date
            ).days

            # Prevent negative cycle times from
            # corrupting the KPI.

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

    # Lower dispute rate means better performance.

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
    # PERFORMANCE TREND
    # ========================================================

    trend = _calculate_supplier_trend(
        supplier_id=supplier_id,
        supplier_pos=supplier_pos,
        supplier_invoices=supplier_invoices,
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

                "total":
                    len(supplier_pos),

                "fulfilled":
                    fulfilled_po_count,

                "on_time":
                    on_time_po_count,

                "late":
                    late_po_count,

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

                "average_fulfillment_time_days":
                    average_fulfillment_time_days,
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

        "trend":
            trend,
    }