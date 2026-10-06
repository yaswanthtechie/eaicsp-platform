from datetime import date, datetime
from enum import Enum

import strawberry

from app.schemas.purchase_order import PurchaseOrderStatus


@strawberry.enum
class GraphQLPurchaseOrderStatus(Enum):
    DRAFT = PurchaseOrderStatus.draft.value
    SENT = PurchaseOrderStatus.sent.value
    ACKNOWLEDGED = PurchaseOrderStatus.acknowledged.value
    FULFILLED = PurchaseOrderStatus.fulfilled.value
    CANCELLED = PurchaseOrderStatus.cancelled.value


@strawberry.type
class PurchaseOrderItemType:
    item_code: str
    description: str
    quantity: int
    unit_price: float


@strawberry.type
class PurchaseOrderHistoryType:
    po_number: str
    supplier_id: str
    actor: str | None
    from_status: GraphQLPurchaseOrderStatus
    to_status: GraphQLPurchaseOrderStatus
    timestamp: datetime


@strawberry.type
class PurchaseOrderType:
    po_number: str
    supplier_id: str
    items: list[PurchaseOrderItemType]
    total_amount: float
    status: GraphQLPurchaseOrderStatus
    created_at: datetime
    expected_delivery: date
    actual_delivery_date: date | None
    history: list[PurchaseOrderHistoryType]


@strawberry.type
class PageInfoType:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type
class PurchaseOrderEdgeType:
    cursor: str
    node: PurchaseOrderType


@strawberry.type
class PurchaseOrderConnectionType:
    edges: list[PurchaseOrderEdgeType]
    page_info: PageInfoType

# ============================================================
# INVOICE GRAPHQL TYPES
# ============================================================

@strawberry.type
class InvoiceLineItemType:
    po_number: str
    item_code: str
    description: str
    quantity: int
    unit_price: float


@strawberry.type
class InvoiceDisputeType:
    reason: str
    actor_id: str
    actor_name: str
    role: str
    timestamp: str
    resolution: str | None
    resolved_by: str | None
    resolved_at: str | None


@strawberry.type
class InvoiceAdjustmentAuditType:
    actor_id: str
    actor_name: str
    role: str
    reason: str
    timestamp: str
    old_amount: float
    new_amount: float
    old_items: list[InvoiceLineItemType]
    new_items: list[InvoiceLineItemType]


@strawberry.type
class InvoiceHistoryType:
    from_status: str | None
    to_status: str
    actor_id: str | None
    actor_name: str | None
    role: str | None
    reason: str | None
    timestamp: str


@strawberry.type
class InvoiceType:
    invoice_number: str
    supplier_id: str
    items: list[InvoiceLineItemType]
    amount: float
    invoice_date: date
    status: str
    dispute: InvoiceDisputeType | None
    adjustment: InvoiceAdjustmentAuditType | None
    document_url: str | None
    history: list[InvoiceHistoryType]


@strawberry.type
class InvoiceEdgeType:
    cursor: str
    node: InvoiceType


@strawberry.type
class InvoiceConnectionType:
    edges: list[InvoiceEdgeType]
    page_info: PageInfoType

# ============================================================
# SUPPLIER DOCUMENT GRAPHQL TYPES
# ============================================================

@strawberry.type
class SupplierDocumentType:
    document_id: str
    supplier_id: str
    document_type: str
    file_name: str
    document_path: str
    status: str
    uploaded_at: datetime
    uploaded_by: str


@strawberry.type
class SupplierDocumentEdgeType:
    cursor: str
    node: SupplierDocumentType


@strawberry.type
class SupplierDocumentConnectionType:
    edges: list[SupplierDocumentEdgeType]
    page_info: PageInfoType