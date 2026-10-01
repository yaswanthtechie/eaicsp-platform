import strawberry
from strawberry.types import Info

from app.services.purchase_order_service import (
    get_purchase_order_by_id,
    acknowledge_purchase_order,
)

from app.graphql.queries import (
    _is_supplier_authorized,
    _to_purchase_order_type,
)
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

        Supplier scoping is enforced inside the resolver
        before any state-changing business logic is executed.
        Existing Purchase Order business logic is reused.
        """

        user = info.context["user"]

        # ====================================================
        # STEP 1: Fetch the PO without changing its state
        # ====================================================

        purchase_order = get_purchase_order_by_id(
            po_number
        )

        if purchase_order is None:
            return None

        # ====================================================
        # STEP 2: Enforce supplier scoping BEFORE mutation
        # ====================================================

        if not _is_supplier_authorized(
            user,
            purchase_order,
        ):
            return None

        # ====================================================
        # STEP 3: Execute existing business logic
        # ====================================================

        acknowledged_po = acknowledge_purchase_order(
            po_number
        )

        if acknowledged_po is None:
            return None

        # ====================================================
        # STEP 4: Convert service result to GraphQL type
        # ====================================================

        return _to_purchase_order_type(
            acknowledged_po
        )