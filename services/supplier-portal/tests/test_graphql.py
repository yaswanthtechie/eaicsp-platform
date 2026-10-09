"""
GraphQL API tests for the Supplier Portal.

Covers:
- GraphQL endpoint/schema
- Purchase-order queries
- Purchase-order supplier scoping
- Purchase-order cursor pagination
- Invoice queries
- Invoice supplier scoping
- Invoice cursor pagination
- Supplier-document queries
- Supplier-document supplier scoping
- Supplier-document cursor pagination
- Supplier without supplier_id
- Acknowledge-PO mutation
- Mutation supplier scoping
- Mutation integrity
"""

from datetime import date, datetime, timezone

import pytest

from app.services.invoice_service import invoices
from app.services.purchase_order_service import (
    purchase_orders,
)
from app.services.supplier_onboarding_service import (
    supplier_documents,
    suppliers,
)
from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.events import SupplierComplianceStatus
from app.services.supplier_compliance_service import (
    supplier_compliance_service,
)


# ============================================================
# GRAPHQL HELPER
# ============================================================


def graphql(
    client,
    query,
    variables=None,
):
    response = client.post(
        "/graphql",
        json={
            "query": query,
            "variables": variables or {},
        },
    )

    assert response.status_code == 200, response.text

    return response.json()


# ============================================================
# TEST DATA HELPERS
# ============================================================

def seed_supplier(
    supplier_id: str = "SUP001",
) -> dict:
    supplier = {
        "supplier_id": supplier_id,
        "supplier_name": f"Test Supplier {supplier_id}",
        "status": "active",
    }

    suppliers[supplier_id] = supplier

    # Round-14:
    # Suppliers created by GraphQL tests must also be visible
    # to the compliance access service.
    supplier.pop("compliance_access_status", None)

    return supplier


def set_compliance_status(
    supplier_id: str,
    status: SupplierComplianceStatus,
):
    """
    Set the Round-14 compliance access state used by
    GraphQL authorization tests.

    These tests intentionally update the in-memory supplier
    state directly. Kafka consumer behavior is tested separately.
    """

    if supplier_id not in suppliers:
        seed_supplier(supplier_id)

    suppliers[supplier_id][
        "compliance_access_status"
    ] = status.value


def seed_po(
    po_number: str,
    supplier_id: str,
    status=PurchaseOrderStatus.draft,
):
    """
    Seed a PO using the structure expected by the existing
    purchase-order service and GraphQL converter.
    """

    seed_supplier(supplier_id)

    po = {
        "po_number": po_number,
        "supplier_id": supplier_id,
        "items": [
            {
                "item_code": "ITEM001",
                "description": "Test Item",
                "quantity": 2,
                "unit_price": 1000,
            }
        ],
        "total_amount": 2000,
        "created_at": datetime(
            2026,
            7,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        "expected_delivery": date(
            2026,
            7,
            30,
        ),
        "status": status,
        "actual_delivery_date": None,
        "history": [],
    }

    purchase_orders[po_number] = po

    return po


def seed_invoice(
    invoice_number: str,
    supplier_id: str,
    status="submitted",
):
    """
    Seed an invoice using the structure expected by the
    existing invoice service and GraphQL converter.
    """

    seed_supplier(supplier_id)

    invoice = {
        "invoice_number": invoice_number,
        "supplier_id": supplier_id,
        "items": [
            {
                "po_number": "PO-GQL-001",
                "item_code": "ITEM001",
                "description": "Test Item",
                "quantity": 2,
                "unit_price": 1000,
            }
        ],
        "amount": 2000,
        "invoice_date": date(
            2026,
            7,
            25,
        ),
        "status": status,
        "dispute": None,
        "adjustment": None,
        "document_url": None,
        "history": [],
    }

    invoices[
        (supplier_id, invoice_number)
    ] = invoice

    return invoice


def seed_document(
    supplier_id: str,
    document_id: str,
    document_type="pan_card",
):
    """
    Seed document metadata directly.

    GraphQL document queries operate on onboarding
    metadata, so MinIO is not required here.
    """

    seed_supplier(supplier_id)

    document = {
        "document_id": document_id,
        "supplier_id": supplier_id,
        "document_type": document_type,
        "file_name": (
            f"{document_type}.pdf"
        ),
        "document_path": (
            "uploads/"
            "supplier_onboarding/"
            f"{supplier_id}/"
            f"{document_type}.pdf"
        ),
        "status": "submitted",
        "uploaded_at": datetime(
            2026,
            7,
            25,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        "uploaded_by": "8",
    }

    supplier_documents.setdefault(
        supplier_id,
        [],
    ).append(document)

    return document


# ============================================================
# FIXTURE CLEANUP
# ============================================================
@pytest.fixture(autouse=True)
def clean_graphql_data():
    purchase_orders.clear()
    invoices.clear()
    suppliers.clear()
    supplier_documents.clear()

    supplier_compliance_service._processed_event_ids.clear()
    supplier_compliance_service._latest_event_times.clear()
    supplier_compliance_service._audit_history.clear()

    # Default authenticated supplier used by supplier_client.
    # GraphQL compliance authorization now validates the
    # supplier before resource lookup.
    seed_supplier("SUP001")

    yield

    purchase_orders.clear()
    invoices.clear()
    suppliers.clear()
    supplier_documents.clear()

    supplier_compliance_service._processed_event_ids.clear()
    supplier_compliance_service._latest_event_times.clear()
    supplier_compliance_service._audit_history.clear()

# ============================================================
# 1. GRAPHQL ENDPOINT / SCHEMA
# ============================================================


def test_graphql_endpoint_is_available(
    supplier_client,
):
    result = graphql(
        supplier_client,
        """
        {
            __typename
        }
        """,
    )

    assert "errors" not in result
    assert result["data"]["__typename"] == "Query"


def test_graphql_schema_exposes_required_query_fields(
    supplier_client,
):
    result = graphql(
        supplier_client,
        """
        {
            __schema {
                queryType {
                    fields {
                        name
                    }
                }
            }
        }
        """,
    )

    assert "errors" not in result

    field_names = {
        field["name"]
        for field in (
            result["data"]
            ["__schema"]
            ["queryType"]
            ["fields"]
        )
    }

    assert "purchaseOrder" in field_names
    assert "purchaseOrders" in field_names
    assert "invoice" in field_names
    assert "invoices" in field_names
    assert "documents" in field_names


def test_graphql_schema_exposes_acknowledge_mutation(
    supplier_client,
):
    result = graphql(
        supplier_client,
        """
        {
            __schema {
                mutationType {
                    fields {
                        name
                    }
                }
            }
        }
        """,
    )

    assert "errors" not in result

    field_names = {
        field["name"]
        for field in (
            result["data"]
            ["__schema"]
            ["mutationType"]
            ["fields"]
        )
    }

    assert (
        "acknowledgePurchaseOrder"
        in field_names
    )


# ============================================================
# 2. PURCHASE ORDER QUERY
# ============================================================


PURCHASE_ORDER_QUERY = """
query GetPurchaseOrder(
    $poNumber: String!
) {
    purchaseOrder(
        poNumber: $poNumber
    ) {
        poNumber
        supplierId
        status
        totalAmount
        createdAt
        expectedDelivery
        actualDeliveryDate
        items {
            itemCode
            description
            quantity
            unitPrice
        }
        history {
            poNumber
            supplierId
            actor
            fromStatus
            toStatus
            timestamp
        }
    }
}
"""


def test_supplier_can_query_own_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-GQL-001",
        "SUP001",
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber": "PO-GQL-001",
        },
    )

    assert "errors" not in result

    po = result["data"]["purchaseOrder"]

    assert po is not None
    assert po["poNumber"] == "PO-GQL-001"
    assert po["supplierId"] == "SUP001"
    assert po["status"] == "DRAFT"
    assert po["totalAmount"] == 2000

    assert len(po["items"]) == 1
    assert po["items"][0]["itemCode"] == "ITEM001"
    assert po["items"][0]["quantity"] == 2
    assert po["items"][0]["unitPrice"] == 1000


def test_query_unknown_purchase_order_returns_null(
    supplier_client,
):
    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber": "DOES-NOT-EXIST",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]["purchaseOrder"]
        is None
    )


def test_supplier_cannot_query_other_supplier_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber": "PO-SUP002-001",
        },
    )

    assert "errors" not in result

    # Critical Milestone 3 security requirement.
    assert (
        result["data"]["purchaseOrder"]
        is None
    )


def test_supplier_b_can_query_own_purchase_order(
    supplier_b_client,
):
    seed_po(
        "PO-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_b_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber": "PO-SUP002-001",
        },
    )

    assert "errors" not in result

    po = result["data"]["purchaseOrder"]

    assert po is not None
    assert po["poNumber"] == "PO-SUP002-001"
    assert po["supplierId"] == "SUP002"


# ============================================================
# 3. PURCHASE ORDER LIST
# ============================================================


PURCHASE_ORDERS_QUERY = """
query GetPurchaseOrders(
    $first: Int,
    $after: String
) {
    purchaseOrders(
        first: $first,
        after: $after
    ) {
        edges {
            cursor
            node {
                poNumber
                supplierId
                status
                totalAmount
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""


def test_purchase_order_list_is_supplier_scoped(
    supplier_client,
):
    seed_po(
        "PO-SUP001-001",
        "SUP001",
    )
    seed_po(
        "PO-SUP001-002",
        "SUP001",
    )
    seed_po(
        "PO-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 10,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["purchaseOrders"]
        ["edges"]
    )

    assert len(edges) == 2

    supplier_ids = {
        edge["node"]["supplierId"]
        for edge in edges
    }

    assert supplier_ids == {"SUP001"}


def test_purchase_order_list_does_not_leak_other_supplier(
    supplier_client,
):
    seed_po(
        "PO-SUP001-001",
        "SUP001",
    )
    seed_po(
        "PO-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["purchaseOrders"]
        ["edges"]
    )

    po_numbers = {
        edge["node"]["poNumber"]
        for edge in edges
    }

    assert "PO-SUP001-001" in po_numbers
    assert "PO-SUP002-001" not in po_numbers


def test_purchase_order_cursor_pagination(
    supplier_client,
):
    seed_po(
        "PO-GQL-001",
        "SUP001",
    )
    seed_po(
        "PO-GQL-002",
        "SUP001",
    )
    seed_po(
        "PO-GQL-003",
        "SUP001",
    )

    first_page = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in first_page

    connection = (
        first_page["data"]
        ["purchaseOrders"]
    )

    assert len(connection["edges"]) == 2
    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is True
    )

    end_cursor = (
        connection["pageInfo"]
        ["endCursor"]
    )

    assert end_cursor is not None

    second_page = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 2,
            "after": end_cursor,
        },
    )

    assert "errors" not in second_page

    second_connection = (
        second_page["data"]
        ["purchaseOrders"]
    )

    assert len(
        second_connection["edges"]
    ) == 1

    assert (
        second_connection["pageInfo"]
        ["hasNextPage"]
        is False
    )


@pytest.mark.parametrize(
    "first",
    [0, -1, 101],
)
def test_purchase_order_pagination_rejects_invalid_first(
    supplier_client,
    first,
):
    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": first,
        },
    )

    assert "errors" in result


def test_purchase_order_pagination_rejects_invalid_cursor(
    supplier_client,
):
    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 10,
            "after": "not-a-valid-cursor",
        },
    )

    assert "errors" in result


# ============================================================
# 4. INVOICE QUERY
# ============================================================


INVOICE_QUERY = """
query GetInvoice(
    $invoiceNumber: String!
) {
    invoice(
        invoiceNumber: $invoiceNumber
    ) {
        invoiceNumber
        supplierId
        status
        amount
        invoiceDate
        documentUrl
        items {
            poNumber
            itemCode
            description
            quantity
            unitPrice
        }
    }
}
"""


def test_supplier_can_query_own_invoice(
    supplier_client,
):
    seed_invoice(
        "INV-GQL-001",
        "SUP001",
    )

    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-GQL-001",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert (
        invoice["invoiceNumber"]
        == "INV-GQL-001"
    )
    assert (
        invoice["supplierId"]
        == "SUP001"
    )
    assert invoice["amount"] == 2000
    assert len(invoice["items"]) == 1
    assert (
        invoice["items"][0]["itemCode"]
        == "ITEM001"
    )


def test_query_unknown_invoice_returns_null(
    supplier_client,
):
    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "DOES-NOT-EXIST",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]["invoice"]
        is None
    )


def test_supplier_cannot_query_other_supplier_invoice(
    supplier_client,
):
    seed_invoice(
        "INV-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-SUP002-001",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]["invoice"]
        is None
    )


def test_supplier_cannot_query_other_supplier_invoice_even_when_both_exist(
    supplier_client,
):
    seed_invoice(
        "INV-SUP001-001",
        "SUP001",
    )

    seed_invoice(
        "INV-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-SUP002-001",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]["invoice"]
        is None
    )


def test_supplier_b_can_query_own_invoice(
    supplier_b_client,
):
    seed_invoice(
        "INV-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_b_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-SUP002-001",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert (
        invoice["invoiceNumber"]
        == "INV-SUP002-001"
    )
    assert (
        invoice["supplierId"]
        == "SUP002"
    )


# ============================================================
# 5. INVOICE LIST
# ============================================================


INVOICES_QUERY = """
query GetInvoices(
    $first: Int,
    $after: String
) {
    invoices(
        first: $first,
        after: $after
    ) {
        edges {
            cursor
            node {
                invoiceNumber
                supplierId
                status
                amount
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""


def test_invoice_list_is_supplier_scoped(
    supplier_client,
):
    seed_invoice(
        "INV-SUP001-001",
        "SUP001",
    )
    seed_invoice(
        "INV-SUP001-002",
        "SUP001",
    )
    seed_invoice(
        "INV-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["invoices"]
        ["edges"]
    )

    assert len(edges) == 2

    supplier_ids = {
        edge["node"]["supplierId"]
        for edge in edges
    }

    assert supplier_ids == {"SUP001"}


def test_invoice_list_does_not_leak_other_supplier(
    supplier_client,
):
    seed_invoice(
        "INV-SUP001-001",
        "SUP001",
    )
    seed_invoice(
        "INV-SUP002-001",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["invoices"]
        ["edges"]
    )

    invoice_numbers = {
        edge["node"]["invoiceNumber"]
        for edge in edges
    }

    assert (
        "INV-SUP001-001"
        in invoice_numbers
    )

    assert (
        "INV-SUP002-001"
        not in invoice_numbers
    )


def test_invoice_cursor_pagination(
    supplier_client,
):
    seed_invoice(
        "INV-GQL-001",
        "SUP001",
    )
    seed_invoice(
        "INV-GQL-002",
        "SUP001",
    )
    seed_invoice(
        "INV-GQL-003",
        "SUP001",
    )

    first_page = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in first_page

    connection = (
        first_page["data"]
        ["invoices"]
    )

    assert len(
        connection["edges"]
    ) == 2

    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is True
    )

    end_cursor = (
        connection["pageInfo"]
        ["endCursor"]
    )

    assert end_cursor is not None

    second_page = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 2,
            "after": end_cursor,
        },
    )

    assert "errors" not in second_page

    second_connection = (
        second_page["data"]
        ["invoices"]
    )

    assert len(
        second_connection["edges"]
    ) == 1

    assert (
        second_connection["pageInfo"]
        ["hasNextPage"]
        is False
    )


@pytest.mark.parametrize(
    "first",
    [0, -1, 101],
)
def test_invoice_pagination_rejects_invalid_first(
    supplier_client,
    first,
):
    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": first,
        },
    )

    assert "errors" in result


def test_invoice_pagination_rejects_invalid_cursor(
    supplier_client,
):
    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 10,
            "after": "invalid-cursor",
        },
    )

    assert "errors" in result


# ============================================================
# 6. SUPPLIER DOCUMENT QUERY
# ============================================================


DOCUMENTS_QUERY = """
query GetDocuments(
    $first: Int,
    $after: String
) {
    documents(
        first: $first,
        after: $after
    ) {
        edges {
            cursor
            node {
                documentId
                supplierId
                documentType
                fileName
                documentPath
                status
                uploadedAt
                uploadedBy
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""


def test_supplier_can_query_own_documents(
    supplier_client,
):
    seed_document(
        "SUP001",
        "DOC-GQL-001",
    )

    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 10,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["documents"]
        ["edges"]
    )

    assert len(edges) == 1

    document = edges[0]["node"]

    assert (
        document["documentId"]
        == "DOC-GQL-001"
    )
    assert (
        document["supplierId"]
        == "SUP001"
    )
    assert (
        document["documentType"]
        == "pan_card"
    )
    assert (
        document["fileName"]
        == "pan_card.pdf"
    )
    assert document["status"] == "submitted"
    assert document["uploadedBy"] == "8"


def test_documents_do_not_leak_other_supplier(
    supplier_client,
):
    seed_document(
        "SUP001",
        "DOC-SUP001-001",
    )

    seed_document(
        "SUP002",
        "DOC-SUP002-001",
    )

    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["documents"]
        ["edges"]
    )

    assert len(edges) == 1

    document_ids = {
        edge["node"]["documentId"]
        for edge in edges
    }

    assert (
        "DOC-SUP001-001"
        in document_ids
    )

    assert (
        "DOC-SUP002-001"
        not in document_ids
    )


def test_supplier_b_can_query_own_documents(
    supplier_b_client,
):
    seed_document(
        "SUP002",
        "DOC-SUP002-001",
    )

    seed_document(
        "SUP001",
        "DOC-SUP001-001",
    )

    result = graphql(
        supplier_b_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["documents"]
        ["edges"]
    )

    assert len(edges) == 1

    assert (
        edges[0]["node"]["supplierId"]
        == "SUP002"
    )


def test_document_cursor_pagination(
    supplier_client,
):
    seed_document(
        "SUP001",
        "DOC-GQL-001",
        "pan_card",
    )

    seed_document(
        "SUP001",
        "DOC-GQL-002",
        "gst_certificate",
    )

    seed_document(
        "SUP001",
        "DOC-GQL-003",
        "bank_certificate",
    )

    first_page = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in first_page

    connection = (
        first_page["data"]
        ["documents"]
    )

    assert len(
        connection["edges"]
    ) == 2

    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is True
    )

    end_cursor = (
        connection["pageInfo"]
        ["endCursor"]
    )

    assert end_cursor is not None

    second_page = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 2,
            "after": end_cursor,
        },
    )

    assert "errors" not in second_page

    second_connection = (
        second_page["data"]
        ["documents"]
    )

    assert len(
        second_connection["edges"]
    ) == 1

    assert (
        second_connection["pageInfo"]
        ["hasNextPage"]
        is False
    )


@pytest.mark.parametrize(
    "first",
    [0, -1, 101],
)
def test_document_pagination_rejects_invalid_first(
    supplier_client,
    first,
):
    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": first,
        },
    )

    assert "errors" in result


def test_document_pagination_rejects_invalid_cursor(
    supplier_client,
):
    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 10,
            "after": "invalid-cursor",
        },
    )

    assert "errors" in result


# ============================================================
# 7. SUPPLIER WITHOUT SUPPLIER_ID
# ============================================================

def test_supplier_without_supplier_id_cannot_query_purchase_orders(
    supplier_no_id_client,
):
    seed_po(
        "PO-SUP001-001",
        "SUP001",
    )

    result = graphql(
        supplier_no_id_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier identity is missing"
        in result["errors"][0]["message"]
    )

def test_supplier_without_supplier_id_cannot_query_single_purchase_order(
    supplier_no_id_client,
):
    seed_po(
        "PO-SUP001-SINGLE",
        "SUP001",
    )

    result = graphql(
        supplier_no_id_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-SUP001-SINGLE",
        },
    )

    assert "errors" in result

    assert (
        "Supplier identity is missing"
        in result["errors"][0]["message"]
    )

def test_supplier_without_supplier_id_cannot_query_invoices(
    supplier_no_id_client,
):
    seed_invoice(
        "INV-SUP001-001",
        "SUP001",
    )

    result = graphql(
        supplier_no_id_client,
        INVOICES_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier identity is missing"
        in result["errors"][0]["message"]
    )

def test_supplier_without_supplier_id_cannot_query_single_invoice(
    supplier_no_id_client,
):
    seed_invoice(
        "INV-SUP001-SINGLE",
        "SUP001",
    )

    result = graphql(
        supplier_no_id_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-SUP001-SINGLE",
        },
    )

    assert "errors" in result

    assert (
        "Supplier identity is missing"
        in result["errors"][0]["message"]
    )

def test_supplier_without_supplier_id_cannot_query_documents(
    supplier_no_id_client,
):
    seed_document(
        "SUP001",
        "DOC-SUP001-001",
    )

    result = graphql(
        supplier_no_id_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier identity is missing"
        in result["errors"][0]["message"]
    )


# ============================================================
# 8. ACKNOWLEDGE PURCHASE ORDER
# ============================================================


ACKNOWLEDGE_MUTATION = """
mutation AcknowledgePurchaseOrder(
    $poNumber: String!
) {
    acknowledgePurchaseOrder(
        poNumber: $poNumber
    ) {
        poNumber
        supplierId
        status
        totalAmount
    }
}
"""


def test_supplier_can_acknowledge_own_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-GQL-ACK-001",
        "SUP001",
        status=PurchaseOrderStatus.sent,
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-GQL-ACK-001",
        },
    )

    assert "errors" not in result

    po = (
        result["data"]
        ["acknowledgePurchaseOrder"]
    )

    assert po is not None

    assert (
        po["poNumber"]
        == "PO-GQL-ACK-001"
    )

    assert (
        po["supplierId"]
        == "SUP001"
    )

    assert (
        po["status"]
        == "ACKNOWLEDGED"
    )

    assert (
        purchase_orders[
            "PO-GQL-ACK-001"
        ]["status"]
        == PurchaseOrderStatus.acknowledged
    )


def test_acknowledge_unknown_purchase_order_returns_null(
    supplier_client,
):
    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "DOES-NOT-EXIST",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]
        ["acknowledgePurchaseOrder"]
        is None
    )


def test_supplier_cannot_acknowledge_other_supplier_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-SUP002-ACK-001",
        "SUP002",
        status=PurchaseOrderStatus.sent,
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-SUP002-ACK-001",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]
        ["acknowledgePurchaseOrder"]
        is None
    )

    assert (
        purchase_orders[
            "PO-SUP002-ACK-001"
        ]["status"]
        == PurchaseOrderStatus.sent
    )


def test_cross_supplier_acknowledge_does_not_modify_purchase_order(
    supplier_client,
):
    po = seed_po(
        "PO-SUP002-ACK-002",
        "SUP002",
        status=PurchaseOrderStatus.sent,
    )

    original_history = list(
        po["history"]
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-SUP002-ACK-002",
        },
    )

    assert "errors" not in result

    assert (
        result["data"]
        ["acknowledgePurchaseOrder"]
        is None
    )

    # Unauthorized mutation must not change
    # the target PO.
    assert (
        purchase_orders[
            "PO-SUP002-ACK-002"
        ]["status"]
        == PurchaseOrderStatus.sent
    )

    assert (
        purchase_orders[
            "PO-SUP002-ACK-002"
        ]["history"]
        == original_history
        == []
    )


def test_supplier_b_can_acknowledge_own_purchase_order(
    supplier_b_client,
):
    seed_po(
        "PO-SUP002-ACK-003",
        "SUP002",
        status=PurchaseOrderStatus.sent,
    )

    result = graphql(
        supplier_b_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-SUP002-ACK-003",
        },
    )

    assert "errors" not in result

    po = (
        result["data"]
        ["acknowledgePurchaseOrder"]
    )

    assert po is not None

    assert (
        po["poNumber"]
        == "PO-SUP002-ACK-003"
    )

    assert (
        po["supplierId"]
        == "SUP002"
    )

    assert (
        po["status"]
        == "ACKNOWLEDGED"
    )


# ============================================================
# 9. CROSS-SUPPLIER COMBINED SECURITY TEST
# ============================================================

def test_supplier_a_cannot_access_supplier_b_graphql_resources(
    supplier_client,
):
    """
    End-to-end resolver-level isolation check.

    Supplier A must not receive:
    - Supplier B PO
    - Supplier B invoice
    - Supplier B documents

    Supplier A is CLEARED, so cross-supplier resources
    must return null/filtered results rather than a
    compliance error.
    """

    # Supplier A is the authenticated supplier.
    # Compliance-first GraphQL authorization requires
    # the authenticated supplier to exist.
    seed_supplier("SUP001")

    # Supplier B owns the resources being requested.
    seed_supplier("SUP002")

    seed_po(
        "PO-SUP002-SECURITY",
        "SUP002",
    )

    seed_invoice(
        "INV-SUP002-SECURITY",
        "SUP002",
    )

    seed_document(
        "SUP002",
        "DOC-SUP002-SECURITY",
    )

    po_result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber": "PO-SUP002-SECURITY",
        },
    )

    invoice_result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber": "INV-SUP002-SECURITY",
        },
    )

    documents_result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    # Supplier A is not suspended, so there should be
    # no compliance authorization error.
    assert "errors" not in po_result
    assert "errors" not in invoice_result
    assert "errors" not in documents_result

    # Supplier A cannot access Supplier B's PO.
    assert (
        po_result["data"]["purchaseOrder"]
        is None
    )

    # Supplier A cannot access Supplier B's invoice.
    assert (
        invoice_result["data"]["invoice"]
        is None
    )

    # Supplier A's document list must not contain
    # Supplier B's document.
    document_ids = {
        edge["node"]["documentId"]
        for edge in (
            documents_result["data"]
            ["documents"]
            ["edges"]
        )
    }

    assert (
        "DOC-SUP002-SECURITY"
        not in document_ids
    )
# ============================================================
# 10. PAGINATION MUST HAPPEN AFTER SUPPLIER FILTERING
# ============================================================


def test_purchase_order_pagination_is_applied_after_supplier_scoping(
    supplier_client,
):
    """
    Security-sensitive pagination test.

    Supplier B records must not consume Supplier A's
    pagination slots.
    """

    seed_po(
        "PO-A-001",
        "SUP001",
    )
    seed_po(
        "PO-A-002",
        "SUP001",
    )

    seed_po(
        "PO-B-001",
        "SUP002",
    )
    seed_po(
        "PO-B-002",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in result

    connection = (
        result["data"]
        ["purchaseOrders"]
    )

    assert len(
        connection["edges"]
    ) == 2

    assert all(
        edge["node"]["supplierId"]
        == "SUP001"
        for edge in connection["edges"]
    )

    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is False
    )


def test_invoice_pagination_is_applied_after_supplier_scoping(
    supplier_client,
):
    """
    Supplier B invoices must not consume Supplier A's
    pagination slots.
    """

    seed_invoice(
        "INV-A-001",
        "SUP001",
    )
    seed_invoice(
        "INV-A-002",
        "SUP001",
    )

    seed_invoice(
        "INV-B-001",
        "SUP002",
    )
    seed_invoice(
        "INV-B-002",
        "SUP002",
    )

    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in result

    connection = (
        result["data"]
        ["invoices"]
    )

    assert len(
        connection["edges"]
    ) == 2

    assert all(
        edge["node"]["supplierId"]
        == "SUP001"
        for edge in connection["edges"]
    )

    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is False
    )


def test_document_pagination_is_applied_after_supplier_scoping(
    supplier_client,
):
    """
    Supplier B documents must not consume Supplier A's
    pagination slots.
    """

    seed_document(
        "SUP001",
        "DOC-A-001",
    )
    seed_document(
        "SUP001",
        "DOC-A-002",
    )

    seed_document(
        "SUP002",
        "DOC-B-001",
    )
    seed_document(
        "SUP002",
        "DOC-B-002",
    )

    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 2,
        },
    )

    assert "errors" not in result

    connection = (
        result["data"]
        ["documents"]
    )

    assert len(
        connection["edges"]
    ) == 2

    assert all(
        edge["node"]["supplierId"]
        == "SUP001"
        for edge in connection["edges"]
    )

    assert (
        connection["pageInfo"]
        ["hasNextPage"]
        is False
    )

def test_internal_role_cannot_acknowledge_purchase_order(
    procurement_client,
):
    seed_po(
        "PO-SUP001-ACK-INT",
        "SUP001",
        status=PurchaseOrderStatus.sent,
    )

    result = graphql(
        procurement_client,
        ACKNOWLEDGE_MUTATION,
        {"poNumber": "PO-SUP001-ACK-INT"},
    )

    assert "errors" in result
    assert "supplier access required" in (
        result["errors"][0]["message"]
    )

    assert (
        purchase_orders["PO-SUP001-ACK-INT"]["status"]
        == PurchaseOrderStatus.sent
    )

    assert (
        purchase_orders["PO-SUP001-ACK-INT"]["history"]
        == []
    )

def test_supplier_invoice_ignores_client_supplier_id(
    supplier_client,
):
    """
    Supplier identity must come from the authenticated user,
    not from the GraphQL supplierId argument.
    """

    seed_invoice(
        "INV-SAME-001",
        "SUP001",
    )

    seed_invoice(
        "INV-SAME-001",
        "SUP002",
    )

    query = """
    query GetInvoice(
        $invoiceNumber: String!,
        $supplierId: String
    ) {
        invoice(
            invoiceNumber: $invoiceNumber,
            supplierId: $supplierId
        ) {
            invoiceNumber
            supplierId
        }
    }
    """

    result = graphql(
        supplier_client,
        query,
        {
            "invoiceNumber": "INV-SAME-001",
            "supplierId": "SUP002",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert invoice["invoiceNumber"] == "INV-SAME-001"

    # Supplier A must still receive Supplier A's invoice.
    assert invoice["supplierId"] == "SUP001"


def test_internal_user_requires_supplier_id_for_single_invoice(
    procurement_client,
):
    """
    Internal users must provide supplierId because invoice
    numbers are scoped by supplier.
    """

    seed_invoice(
        "INV-INTERNAL-001",
        "SUP001",
    )

    result = graphql(
        procurement_client,
        INVOICE_QUERY,
        {
            "invoiceNumber": "INV-INTERNAL-001",
        },
    )

    assert "errors" in result

    assert (
        "supplierId is required for internal users."
        in result["errors"][0]["message"]
    )

    assert result["data"]["invoice"] is None


def test_internal_user_can_query_invoice_with_supplier_id(
    procurement_client,
):
    """
    Internal users can retrieve an invoice when both the
    supplier ID and invoice number are supplied.
    """

    seed_invoice(
        "INV-INTERNAL-002",
        "SUP001",
    )

    result = graphql(
        procurement_client,
        """
        query GetInvoice(
            $invoiceNumber: String!,
            $supplierId: String!
        ) {
            invoice(
                invoiceNumber: $invoiceNumber,
                supplierId: $supplierId
            ) {
                invoiceNumber
                supplierId
                amount
            }
        }
        """,
        {
            "invoiceNumber": "INV-INTERNAL-002",
            "supplierId": "SUP001",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert invoice["invoiceNumber"] == "INV-INTERNAL-002"
    assert invoice["supplierId"] == "SUP001"
    assert invoice["amount"] == 2000


def test_internal_user_gets_correct_invoice_when_invoice_number_is_shared(
    procurement_client,
):
    """
    Invoice numbers are scoped by supplier.

    The same invoice number can exist for multiple suppliers.
    Internal users must receive the invoice belonging to the
    explicitly requested supplier.
    """

    seed_invoice(
        "INV-SHARED-001",
        "SUP001",
    )

    seed_invoice(
        "INV-SHARED-001",
        "SUP002",
    )

    result = graphql(
        procurement_client,
        """
        query GetInvoice(
            $invoiceNumber: String!,
            $supplierId: String!
        ) {
            invoice(
                invoiceNumber: $invoiceNumber,
                supplierId: $supplierId
            ) {
                invoiceNumber
                supplierId
                amount
            }
        }
        """,
        {
            "invoiceNumber": "INV-SHARED-001",
            "supplierId": "SUP002",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert invoice["invoiceNumber"] == "INV-SHARED-001"
    assert invoice["supplierId"] == "SUP002"
    assert invoice["amount"] == 2000

# ============================================================
# 11. ROUND-14 COMPLIANCE ACCESS ENFORCEMENT
# ============================================================


def test_cleared_supplier_can_query_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-R14-CLEAR-001",
        "SUP001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.cleared,
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-R14-CLEAR-001",
        },
    )

    assert "errors" not in result

    po = result["data"]["purchaseOrder"]

    assert po is not None
    assert po["supplierId"] == "SUP001"


def test_needs_review_supplier_can_query_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-R14-REVIEW-001",
        "SUP001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.needs_review,
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-R14-REVIEW-001",
        },
    )

    assert "errors" not in result

    po = result["data"]["purchaseOrder"]

    assert po is not None
    assert po["supplierId"] == "SUP001"


def test_suspended_supplier_cannot_query_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-R14-BLOCK-001",
        "SUP001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-R14-BLOCK-001",
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    assert (
        result["data"]["purchaseOrder"]
        is None
    )

def test_suspended_supplier_cannot_query_purchase_order_list(
    supplier_client,
):
    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    # Strawberry returns data=None when the root resolver
    # raises PermissionError.
    assert result["data"] is None


def test_needs_review_supplier_can_query_invoices(
    supplier_client,
):
    seed_invoice(
        "INV-R14-REVIEW-001",
        "SUP001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.needs_review,
    )

    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-R14-REVIEW-001",
        },
    )

    assert "errors" not in result

    invoice = result["data"]["invoice"]

    assert invoice is not None
    assert invoice["supplierId"] == "SUP001"


def test_suspended_supplier_cannot_query_invoice(
    supplier_client,
):
    seed_invoice(
        "INV-R14-BLOCK-001",
        "SUP001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-R14-BLOCK-001",
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    assert (
        result["data"]["invoice"]
        is None
    )

def test_suspended_supplier_cannot_query_invoice_list(
    supplier_client,
):
    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    assert result["data"] is None

def test_needs_review_supplier_can_query_documents(
    supplier_client,
):
    seed_document(
        "SUP001",
        "DOC-R14-REVIEW-001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.needs_review,
    )

    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" not in result

    edges = (
        result["data"]
        ["documents"]
        ["edges"]
    )

    assert len(edges) == 1

    assert (
        edges[0]["node"]["supplierId"]
        == "SUP001"
    )

def test_suspended_supplier_cannot_query_documents(
    supplier_client,
):
    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    assert result["data"] is None
    
def test_needs_review_supplier_cannot_acknowledge_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-R14-REVIEW-ACK-001",
        "SUP001",
        status=PurchaseOrderStatus.sent,
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.needs_review,
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-R14-REVIEW-ACK-001",
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is under compliance review"
        in result["errors"][0]["message"]
    )

    # The PO must remain unchanged.
    assert (
        purchase_orders[
            "PO-R14-REVIEW-ACK-001"
        ]["status"]
        == PurchaseOrderStatus.sent
    )

    assert (
        purchase_orders[
            "PO-R14-REVIEW-ACK-001"
        ]["history"]
        == []
    )


def test_suspended_supplier_cannot_acknowledge_purchase_order(
    supplier_client,
):
    seed_po(
        "PO-R14-BLOCK-ACK-001",
        "SUP001",
        status=PurchaseOrderStatus.sent,
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-R14-BLOCK-ACK-001",
        },
    )

    assert "errors" in result

    assert (
        "Supplier account is suspended due to compliance status"
        in result["errors"][0]["message"]
    )

    # The PO must remain unchanged.
    assert (
        purchase_orders[
            "PO-R14-BLOCK-ACK-001"
        ]["status"]
        == PurchaseOrderStatus.sent
    )

    assert (
        purchase_orders[
            "PO-R14-BLOCK-ACK-001"
        ]["history"]
        == []
    )


def test_cleared_supplier_can_acknowledge_purchase_order_after_compliance_check(
    supplier_client,
):
    seed_po(
        "PO-R14-CLEAR-ACK-001",
        "SUP001",
        status=PurchaseOrderStatus.sent,
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.cleared,
    )

    result = graphql(
        supplier_client,
        ACKNOWLEDGE_MUTATION,
        {
            "poNumber":
                "PO-R14-CLEAR-ACK-001",
        },
    )

    assert "errors" not in result

    po = (
        result["data"]
        ["acknowledgePurchaseOrder"]
    )

    assert po is not None

    assert (
        po["status"]
        == "ACKNOWLEDGED"
    )

    assert (
        purchase_orders[
            "PO-R14-CLEAR-ACK-001"
        ]["status"]
        == PurchaseOrderStatus.acknowledged
    )


def test_suspended_supplier_cannot_access_any_graphql_resource(
    supplier_client,
):
    """
    Combined Round-14 enforcement test.

    A suspended supplier must not access:
    - single PO
    - PO list
    - single invoice
    - invoice list
    - documents
    """

    seed_po(
        "PO-R14-COMBINED-001",
        "SUP001",
    )

    seed_invoice(
        "INV-R14-COMBINED-001",
        "SUP001",
    )

    seed_document(
        "SUP001",
        "DOC-R14-COMBINED-001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    po_result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-R14-COMBINED-001",
        },
    )

    po_list_result = graphql(
        supplier_client,
        PURCHASE_ORDERS_QUERY,
        {
            "first": 100,
        },
    )

    invoice_result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-R14-COMBINED-001",
        },
    )

    invoice_list_result = graphql(
        supplier_client,
        INVOICES_QUERY,
        {
            "first": 100,
        },
    )

    document_result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    expected_message = (
        "Supplier account is suspended due to "
        "compliance status"
    )

    for result in [
        po_result,
        po_list_result,
        invoice_result,
        invoice_list_result,
        document_result,
    ]:
        assert "errors" in result
        assert (
            expected_message
            in result["errors"][0]["message"]
        )


def test_suspended_supplier_cannot_access_other_supplier_resources(
    supplier_client,
):
    """
    Compliance suspension must be enforced before the normal
    supplier-resource lookup/scoping logic.
    """

    seed_po(
        "PO-R14-OTHER-001",
        "SUP002",
    )

    seed_invoice(
        "INV-R14-OTHER-001",
        "SUP002",
    )

    seed_document(
        "SUP002",
        "DOC-R14-OTHER-001",
    )

    set_compliance_status(
        "SUP001",
        SupplierComplianceStatus.suspended,
    )

    po_result = graphql(
        supplier_client,
        PURCHASE_ORDER_QUERY,
        {
            "poNumber":
                "PO-R14-OTHER-001",
        },
    )

    invoice_result = graphql(
        supplier_client,
        INVOICE_QUERY,
        {
            "invoiceNumber":
                "INV-R14-OTHER-001",
        },
    )

    documents_result = graphql(
        supplier_client,
        DOCUMENTS_QUERY,
        {
            "first": 100,
        },
    )

    expected_message = (
        "Supplier account is suspended due to "
        "compliance status"
    )

    assert "errors" in po_result
    assert (
        expected_message
        in po_result["errors"][0]["message"]
    )

    assert "errors" in invoice_result
    assert (
        expected_message
        in invoice_result["errors"][0]["message"]
    )

    assert "errors" in documents_result
    assert (
        expected_message
        in documents_result["errors"][0]["message"]
    )
