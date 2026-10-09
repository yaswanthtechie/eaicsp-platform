import base64
import binascii
from datetime import datetime
from typing import Any, Callable

import strawberry
from strawberry.types import Info

from app.graphql.context import require_graphql_view_access

from app.graphql.types import (
    GraphQLPurchaseOrderStatus,
    InvoiceAdjustmentAuditType,
    InvoiceConnectionType,
    InvoiceDisputeType,
    InvoiceEdgeType,
    InvoiceHistoryType,
    InvoiceLineItemType,
    InvoiceType,
    PageInfoType,
    PurchaseOrderConnectionType,
    PurchaseOrderEdgeType,
    PurchaseOrderHistoryType,
    PurchaseOrderItemType,
    PurchaseOrderType,
    SupplierDocumentConnectionType,
    SupplierDocumentEdgeType,
    SupplierDocumentType,
)

from app.schemas.invoice import InvoiceStatus

from app.services.invoice_service import (
    get_all_invoices,
    get_invoice_by_number,
)

from app.services.purchase_order_service import (
    get_all_purchase_orders,
    get_purchase_order_by_id,
)

from app.services.supplier_onboarding_service import (
    list_supplier_documents,
    supplier_documents,
)


# ============================================================
# CURSOR HELPERS
# ============================================================


def _encode_cursor(index: int) -> str:
    """Encode a list index as an opaque GraphQL cursor."""

    value = str(index).encode("utf-8")

    return base64.b64encode(value).decode("utf-8")


def _decode_cursor(cursor: str) -> int:
    """Decode a GraphQL cursor into a list index."""

    try:
        value = base64.b64decode(
            cursor.encode("utf-8"),
            validate=True,
        ).decode("utf-8")

        index = int(value)

        if index < 0:
            raise ValueError

        return index

    except (
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
    ) as exc:
        raise ValueError("Invalid cursor.") from exc


def _paginate(
    items: list[dict],
    first: int,
    after: str | None,
    edge_factory: Callable[[str, dict], Any],
):
    """
    Apply cursor pagination to an already-authorized list.

    Supplier filtering must happen before this function is called.
    """

    if first < 1:
        raise ValueError(
            "The 'first' argument must be greater than 0."
        )

    if first > 100:
        raise ValueError(
            "The 'first' argument cannot be greater than 100."
        )

    start_index = 0

    if after is not None:
        cursor_index = _decode_cursor(after)

        if cursor_index >= len(items):
            raise ValueError("Invalid cursor.")

        start_index = cursor_index + 1

    page_items = items[
        start_index:start_index + first
    ]

    edges = []

    for offset, item in enumerate(
        page_items,
        start=start_index,
    ):
        edges.append(
            edge_factory(
                _encode_cursor(offset),
                item,
            )
        )

    end_cursor = (
        edges[-1].cursor
        if edges
        else None
    )

    has_next_page = (
        start_index + first < len(items)
    )

    return edges, PageInfoType(
        has_next_page=has_next_page,
        end_cursor=end_cursor,
    )


# ============================================================
# PURCHASE ORDER CONVERSION
# ============================================================


def _to_purchase_order_type(
    purchase_order: dict,
) -> PurchaseOrderType:
    """Convert a Supplier Portal PO dictionary to GraphQL."""

    items = [
        PurchaseOrderItemType(
            item_code=item["item_code"],
            description=item["description"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )
        for item in purchase_order.get("items", [])
    ]

    history = []

    for event in purchase_order.get("history", []):
        timestamp = event["timestamp"]

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        from_status = event["from_status"]
        to_status = event["to_status"]

        if hasattr(from_status, "value"):
            from_status = from_status.value

        if hasattr(to_status, "value"):
            to_status = to_status.value

        history.append(
            PurchaseOrderHistoryType(
                po_number=event["po_number"],
                supplier_id=event["supplier_id"],
                actor=event.get("actor"),
                from_status=GraphQLPurchaseOrderStatus(
                    from_status
                ),
                to_status=GraphQLPurchaseOrderStatus(
                    to_status
                ),
                timestamp=timestamp,
            )
        )

    status = purchase_order["status"]

    if hasattr(status, "value"):
        status = status.value

    return PurchaseOrderType(
        po_number=purchase_order["po_number"],
        supplier_id=purchase_order["supplier_id"],
        items=items,
        total_amount=purchase_order["total_amount"],
        status=GraphQLPurchaseOrderStatus(status),
        created_at=purchase_order["created_at"],
        expected_delivery=purchase_order["expected_delivery"],
        actual_delivery_date=purchase_order.get(
            "actual_delivery_date"
        ),
        history=history,
    )


# ============================================================
# PURCHASE ORDER SUPPLIER SCOPING
# ============================================================


def _is_supplier_authorized(
    user: dict,
    purchase_order: dict,
) -> bool:
    """
    Supplier users may only access their own supplier's PO.

    Non-supplier roles are not restricted here.
    """

    if user.get("role") != "supplier":
        return True

    user_supplier_id = user.get("supplier_id")
    resource_supplier_id = purchase_order.get(
        "supplier_id"
    )

    if not user_supplier_id:
        return False

    return user_supplier_id == resource_supplier_id


# ============================================================
# INVOICE STATUS
# ============================================================


def _normalize_invoice_status(status) -> str:
    """Convert InvoiceStatus enum or string to GraphQL string."""

    if isinstance(status, InvoiceStatus):
        return status.value

    return str(status)


# ============================================================
# INVOICE CONVERSION
# ============================================================


def _to_invoice_type(
    invoice: dict,
) -> InvoiceType:
    """Convert a Supplier Portal invoice dictionary to GraphQL."""

    items = [
        InvoiceLineItemType(
            po_number=item["po_number"],
            item_code=item["item_code"],
            description=item["description"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )
        for item in invoice.get("items", [])
    ]

    # --------------------------------------------------------
    # Dispute
    # --------------------------------------------------------

    dispute = None
    dispute_data = invoice.get("dispute")

    if dispute_data is not None:
        dispute = InvoiceDisputeType(
            reason=dispute_data["reason"],
            actor_id=dispute_data["actor_id"],
            actor_name=dispute_data["actor_name"],
            role=dispute_data["role"],
            timestamp=dispute_data["timestamp"],
            resolution=dispute_data.get("resolution"),
            resolved_by=dispute_data.get("resolved_by"),
            resolved_at=dispute_data.get("resolved_at"),
        )

    # --------------------------------------------------------
    # Adjustment
    # --------------------------------------------------------

    adjustment = None
    adjustment_data = invoice.get("adjustment")

    if adjustment_data is not None:
        old_items = [
            InvoiceLineItemType(
                po_number=item["po_number"],
                item_code=item["item_code"],
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            for item in adjustment_data.get(
                "old_items",
                [],
            )
        ]

        new_items = [
            InvoiceLineItemType(
                po_number=item["po_number"],
                item_code=item["item_code"],
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            for item in adjustment_data.get(
                "new_items",
                [],
            )
        ]

        adjustment = InvoiceAdjustmentAuditType(
            actor_id=adjustment_data["actor_id"],
            actor_name=adjustment_data["actor_name"],
            role=adjustment_data["role"],
            reason=adjustment_data["reason"],
            timestamp=adjustment_data["timestamp"],
            old_amount=adjustment_data["old_amount"],
            new_amount=adjustment_data["new_amount"],
            old_items=old_items,
            new_items=new_items,
        )

    # --------------------------------------------------------
    # History
    # --------------------------------------------------------

    history = []

    for event in invoice.get("history", []):
        from_status = event.get("from_status")
        to_status = event["to_status"]

        if hasattr(from_status, "value"):
            from_status = from_status.value

        if hasattr(to_status, "value"):
            to_status = to_status.value

        history.append(
            InvoiceHistoryType(
                from_status=from_status,
                to_status=to_status,
                actor_id=event.get("actor_id"),
                actor_name=event.get("actor_name"),
                role=event.get("role"),
                reason=event.get("reason"),
                timestamp=event["timestamp"],
            )
        )

    return InvoiceType(
        invoice_number=invoice["invoice_number"],
        supplier_id=invoice["supplier_id"],
        items=items,
        amount=invoice["amount"],
        invoice_date=invoice["invoice_date"],
        status=_normalize_invoice_status(
            invoice["status"]
        ),
        dispute=dispute,
        adjustment=adjustment,
        document_url=invoice.get("document_url"),
        history=history,
    )


# ============================================================
# INVOICE SUPPLIER SCOPING
# ============================================================


def _is_invoice_authorized(
    user: dict,
    invoice: dict,
) -> bool:
    """
    Supplier users may only access their own supplier's invoice.
    """

    if user.get("role") != "supplier":
        return True

    user_supplier_id = user.get("supplier_id")
    resource_supplier_id = invoice.get(
        "supplier_id"
    )

    if not user_supplier_id:
        return False

    return user_supplier_id == resource_supplier_id


# ============================================================
# SUPPLIER DOCUMENT CONVERSION
# ============================================================


def _to_supplier_document_type(
    document: dict,
) -> SupplierDocumentType:
    """Convert a supplier document dictionary to GraphQL."""

    status = document["status"]

    if hasattr(status, "value"):
        status = status.value

    return SupplierDocumentType(
        document_id=str(document["document_id"]),
        supplier_id=str(document["supplier_id"]),
        document_type=str(document["document_type"]),
        file_name=str(document["file_name"]),
        document_path=str(document["document_path"]),
        status=str(status),
        uploaded_at=document["uploaded_at"],
        uploaded_by=str(document["uploaded_by"]),
    )


# ============================================================
# SUPPLIER DOCUMENT SUPPLIER SCOPING
# ============================================================


def _get_authorized_documents(
    user: dict,
) -> list[dict]:
    """
    Return only documents the authenticated user is allowed
    to access.

    Supplier users are restricted to their own supplier.
    Non-supplier roles can access documents across suppliers.
    """

    if user.get("role") == "supplier":
        supplier_id = user.get("supplier_id")

        if not supplier_id:
            return []

        try:
            return list(
                list_supplier_documents(
                    supplier_id
                )
            )
        except ValueError:
            # Do not expose information when the supplier
            # referenced by the token does not exist.
            return []

    return [
        document
        for documents in supplier_documents.values()
        for document in documents
    ]


# ============================================================
# GRAPHQL QUERY ROOT
# ============================================================


@strawberry.type
class Query:

    # ========================================================
    # SINGLE PURCHASE ORDER
    # ========================================================

    @strawberry.field
    def purchase_order(
        self,
        info: Info,
        po_number: str,
    ) -> PurchaseOrderType | None:
        user = info.context["user"]

        # ----------------------------------------------------
        # Round-14 compliance enforcement
        # ----------------------------------------------------
        #
        # This MUST happen before resource lookup.
        #
        # Result:
        #   CLEARED      -> allowed
        #   NEEDS_REVIEW -> allowed to view
        #   SUSPENDED    -> rejected
        #
        # This also guarantees that a suspended supplier
        # cannot probe another supplier's resource.
        require_graphql_view_access(user)

        purchase_order = get_purchase_order_by_id(
            po_number
        )

        # Existing GraphQL contract:
        # unknown PO -> null without an error.
        if purchase_order is None:
            return None

        # Existing supplier isolation:
        # cross-supplier PO -> null without an error.
        if not _is_supplier_authorized(
            user,
            purchase_order,
        ):
            return None

        return _to_purchase_order_type(
            purchase_order
        )

    # ========================================================
    # PURCHASE ORDERS
    # ========================================================

    @strawberry.field
    def purchase_orders(
        self,
        info: Info,
        first: int = 10,
        after: str | None = None,
    ) -> PurchaseOrderConnectionType:
        user = info.context["user"]

        # Compliance is checked before exposing the collection.
        require_graphql_view_access(user)

        all_purchase_orders = get_all_purchase_orders()

        # IMPORTANT:
        # Supplier filtering happens BEFORE pagination.
        if user.get("role") == "supplier":
            supplier_id = user.get("supplier_id")

            if not supplier_id:
                all_purchase_orders = []
            else:
                all_purchase_orders = [
                    purchase_order
                    for purchase_order in all_purchase_orders
                    if purchase_order.get(
                        "supplier_id"
                    ) == supplier_id
                ]

        edges, page_info = _paginate(
            all_purchase_orders,
            first,
            after,
            lambda cursor, purchase_order:
                PurchaseOrderEdgeType(
                    cursor=cursor,
                    node=_to_purchase_order_type(
                        purchase_order
                    ),
                ),
        )

        return PurchaseOrderConnectionType(
            edges=edges,
            page_info=page_info,
        )

    # ========================================================
    # SINGLE INVOICE
    # ========================================================

    @strawberry.field
    def invoice(
        self,
        info: Info,
        invoice_number: str,
        supplier_id: str | None = None,
    ) -> InvoiceType | None:
        """
        Return a single invoice.

        Supplier users:
            - compliance is checked before resource lookup;
            - supplier_id comes only from the authenticated context;
            - client-supplied supplierId is ignored;
            - supplier ownership is verified after lookup.

        Internal users:
            - supplier_id must be explicitly supplied;
            - lookup uses supplier_id + invoice_number.
        """

        user = info.context["user"]

        # ----------------------------------------------------
        # Supplier users
        # ----------------------------------------------------

        if user.get("role") == "supplier":
            # IMPORTANT:
            # Check compliance BEFORE looking up the invoice.
            #
            # This ensures:
            #   - missing supplier_id -> error
            #   - suspended supplier -> error
            #   - needs_review -> view allowed
            #   - cleared -> view allowed
            require_graphql_view_access(user)

            authenticated_supplier_id = user.get(
                "supplier_id"
            )

            # require_graphql_view_access already validates
            # supplier identity, but keep this guard defensive.
            if not authenticated_supplier_id:
                raise PermissionError(
                    "Supplier identity is missing"
                )

            try:
                invoice = get_invoice_by_number(
                    supplier_id=authenticated_supplier_id,
                    invoice_number=invoice_number,
                )
            except ValueError:
                # Preserve existing GraphQL behavior:
                # unknown invoice -> null.
                return None

            # Preserve supplier isolation.
            if not _is_invoice_authorized(
                user,
                invoice,
            ):
                return None

            return _to_invoice_type(invoice)

        # ----------------------------------------------------
        # Internal users
        # ----------------------------------------------------

        if not supplier_id:
            raise ValueError(
                "supplierId is required for internal users."
            )

        try:
            invoice = get_invoice_by_number(
                supplier_id=supplier_id,
                invoice_number=invoice_number,
            )
        except ValueError:
            return None

        return _to_invoice_type(invoice)

    # ========================================================
    # INVOICES
    # ========================================================

    @strawberry.field
    def invoices(
        self,
        info: Info,
        first: int = 10,
        after: str | None = None,
    ) -> InvoiceConnectionType:
        user = info.context["user"]

        # Compliance applies before exposing the collection.
        require_graphql_view_access(user)

        all_invoices = get_all_invoices()

        # IMPORTANT:
        # Supplier filtering happens BEFORE pagination.
        if user.get("role") == "supplier":
            supplier_id = user.get("supplier_id")

            if not supplier_id:
                all_invoices = []
            else:
                all_invoices = [
                    invoice
                    for invoice in all_invoices
                    if invoice.get(
                        "supplier_id"
                    ) == supplier_id
                ]

        edges, page_info = _paginate(
            all_invoices,
            first,
            after,
            lambda cursor, invoice:
                InvoiceEdgeType(
                    cursor=cursor,
                    node=_to_invoice_type(
                        invoice
                    ),
                ),
        )

        return InvoiceConnectionType(
            edges=edges,
            page_info=page_info,
        )

    # ========================================================
    # SUPPLIER DOCUMENTS
    # ========================================================

    @strawberry.field
    def documents(
        self,
        info: Info,
        first: int = 10,
        after: str | None = None,
    ) -> SupplierDocumentConnectionType:
        user = info.context["user"]

        # IMPORTANT:
        # Compliance is checked BEFORE any document lookup.
        #
        # Therefore:
        #   CLEARED      -> documents allowed
        #   NEEDS_REVIEW -> documents allowed
        #   SUSPENDED    -> immediately rejected
        #
        # This is important for Round-14 because suspended
        # suppliers must not reach document storage logic.
        require_graphql_view_access(user)

        documents = _get_authorized_documents(user)

        # Authorization/filtering occurs before pagination.
        edges, page_info = _paginate(
            documents,
            first,
            after,
            lambda cursor, document:
                SupplierDocumentEdgeType(
                    cursor=cursor,
                    node=_to_supplier_document_type(
                        document
                    ),
                ),
        )

        return SupplierDocumentConnectionType(
            edges=edges,
            page_info=page_info,
        )
