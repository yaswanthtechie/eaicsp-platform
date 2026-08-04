from datetime import datetime

from app.services.purchase_order_service import purchase_orders
from app.services.invoice_service import invoices


def get_supplier_stats(supplier_id: str):

    supplier_purchase_orders = [
        po
        for po in purchase_orders.values()
        if po["supplier_id"] == supplier_id
    ]

    # Supplier not found
    if not supplier_purchase_orders:
        raise ValueError(
            f"Supplier '{supplier_id}' not found."
        )

    po_count = len(supplier_purchase_orders)

    # -----------------------------
    # On-time delivery percentage
    # -----------------------------
    on_time_count = 0

    for po in supplier_purchase_orders:

     actual_delivery = po.get(
        "actual_delivery_date"
        )

     expected_delivery = po.get(
       "expected_delivery"
      )

     if actual_delivery is None:
         continue

     if actual_delivery <= expected_delivery:
      on_time_count += 1

    on_time_percentage = (
    on_time_count / po_count
    ) * 100

    # -----------------------------
    # Average invoice cycle time
    # -----------------------------
    cycle_times = []

    for invoice in invoices.values():

        if invoice["supplier_id"] != supplier_id:
            continue

        purchase_order = purchase_orders.get(
            invoice["po_number"]
        )

        if purchase_order is None:
            continue

        created_at = purchase_order["created_at"]

        if isinstance(created_at, str):
         created_date = datetime.fromisoformat(
        created_at
        ).date()
        else:
         created_date = created_at.date()

        invoice_date = invoice["invoice_date"]

        if isinstance(invoice_date, str):
         invoice_date = datetime.fromisoformat(
        invoice_date
        ).date()

        cycle_days = (
        invoice_date - created_date
        ).days

        cycle_times.append(cycle_days)

    average_invoice_cycle_time = 0.0

    if cycle_times:
        average_invoice_cycle_time = (
            sum(cycle_times)
            / len(cycle_times)
        )

    return {
        "supplier_id": supplier_id,
        "po_count": po_count,
        "on_time_percentage": round(
            on_time_percentage,
            2
        ),
        "average_invoice_cycle_time": round(
            average_invoice_cycle_time,
            2
        ),
    }