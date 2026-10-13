import strawberry
from strawberry.types import Info

from app.services.purchase_order_service import (
    get_purchase_order_by_id,
    acknowledge_purchase_order,
)

from app.graphql.context import require_graphql_write_access
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

        Round-14 compliance rules:
            - CLEARED supplier: allowed
            - NEEDS REVIEW supplier: denied
            - SUSPENDED supplier: denied

        Existing rules remain unchanged:
            - Only supplier users may acknowledge.
            - Supplier ownership is enforced.
            - Unknown/other-supplier POs return null.
            - Business state changes happen only after authorization.
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
        #
        # IMPORTANT:
        # We intentionally perform resource lookup and ownership
        # checks before compliance lookup.
        #
        # This preserves the existing GraphQL contract:
        #   - unknown PO -> null
        #   - another supplier's PO -> null
        #
        # It also prevents a compliance lookup from turning an
        # unknown/cross-supplier resource into a different error.

        purchase_order = get_purchase_order_by_id(
            po_number
        )

        if purchase_order is None:
            return None

        # ====================================================
        # STEP 4: Enforce supplier ownership
        # ====================================================

        if purchase_order.get("supplier_id") != supplier_id:
            return None

        # ====================================================
        # STEP 5: Round-14 compliance write access
        # ====================================================
        #
        # CLEARED       -> continue
        # NEEDS REVIEW  -> reject
        # SUSPENDED     -> reject
        #
        # This MUST happen before the state-changing business
        # operation below.

        require_graphql_write_access(user)

        # ====================================================
        # STEP 6: Execute existing business logic
        # ====================================================

        acknowledged_po = acknowledge_purchase_order(
            po_number
        )

        if acknowledged_po is None:
            return None

        # ====================================================
        # STEP 7: Convert service result to GraphQL type
        # ====================================================

        return _to_purchase_order_type(
            acknowledged_po
        )
