import strawberry
from strawberry.types import Info

from app.services.purchase_order_service import (
    get_purchase_order_by_id,
    acknowledge_purchase_order,
)

from app.graphql.queries import _to_purchase_order_type
from app.graphql.types import PurchaseOrderType


@strawberry.type
class Mutation:

    @strawberry.mutation
    def acknowledge_purchase_order(
        self,
        info: Info,
        po_number: str,
    ) -> PurchaseOrderType | None:
        """
        Acknowledge a Purchase Order.

        Mirrors the REST endpoint (require_po_access(supplier_only=True)):
        only the supplier that owns the PO may acknowledge it.

        Internal roles are rejected and cannot acknowledge supplier POs.
        Ownership is checked before any state-changing business logic.
        """

        user = info.context["user"]

        # ====================================================
        # STEP 1: Only supplier users may acknowledge
        # ====================================================

        if user.get("role") != "supplier":
            raise PermissionError(
                "Forbidden: supplier access required"
            )

        # ====================================================
        # STEP 2: Supplier identity is mandatory
        # ====================================================

        supplier_id = user.get("supplier_id")

        if not supplier_id:
            raise PermissionError(
                "Supplier identity is missing"
            )

        # ====================================================
        # STEP 3: Fetch PO without changing its state
        # ====================================================

        purchase_order = get_purchase_order_by_id(
            po_number
        )

        # Unknown PO and another supplier's PO intentionally
        # look the same to the caller.
        if (
            purchase_order is None
            or purchase_order.get("supplier_id") != supplier_id
        ):
            return None

        # ====================================================
        # STEP 4: Execute existing business logic
        # ====================================================

        acknowledged_po = acknowledge_purchase_order(
            po_number
        )

        if acknowledged_po is None:
            return None

        # ====================================================
        # STEP 5: Convert service result to GraphQL type
        # ====================================================

        return _to_purchase_order_type(
            acknowledged_po
        )