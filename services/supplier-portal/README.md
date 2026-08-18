# Enterprise AI Cognitive Supply Chain Platform

## Supplier Portal Service

A FastAPI-based backend microservice for managing **Purchase Orders, supplier invoices, invoice documents, Purchase Order lifecycle transitions, audit history, supplier operational statistics, and supplier performance scorecards**.

The service was implemented incrementally across four major development :

1. **1 — Purchase Order Management and Lifecycle**
2. **2 — Invoice Management and Document Security**
3. **3 — Supplier Statistics**
4. **4 — Supplier Performance Scorecard**

The implementation currently uses **in-memory storage** and local file storage. The service is designed so that persistent database and infrastructure components can be introduced in a later phase.

---

# 1. Project Objective

The Supplier Portal Service provides backend APIs for the supplier/procurement workflow:

```text
                    PURCHASE ORDER
                         │
                         ▼
                      Draft
                         │
                         ▼
                       Sent
                         │
                         ▼
                   Acknowledged
                         │
                         ▼
                     Fulfilled
                         │
                         ▼
                      Invoice
                         │
                         ▼
                  Invoice Validation
                         │
                         ▼
                   PDF Document
                         │
                         ▼
               Supplier Performance
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       Supplier Stats           Scorecard
```

The service focuses on four areas:

* Purchase Order lifecycle management
* Invoice validation and document management
* Supplier operational statistics
* Supplier performance scorecard

---

# 2. Technology Stack

| Technology   | Purpose                         |
| ------------ | ------------------------------- |
| Python 3.14  | Backend programming language    |
| FastAPI      | REST API framework              |
| Pydantic     | Request/response validation     |
| Uvicorn      | ASGI application server         |
| Pytest       | Automated testing               |
| HTTPX        | FastAPI TestClient support      |
| pathlib      | Secure filesystem path handling |
| FileResponse | Invoice PDF download            |

---

# 3. Development 

| no  | Module              | Main Responsibility                                                 |
| ------ | ------------------- | ------------------------------------------------------------------- |
|  1     | Purchase Orders     | PO CRUD, lifecycle, transitions, audit history                      |
|  2     | Invoices            | Invoice validation, tolerance, duplicate protection, PDF management |
|  3     | Supplier Statistics | PO count, on-time %, invoice cycle time                             |
|  4     | Supplier Scorecard  | On-time %, dispute rate, invoice accuracy, overall supplier score   |

---

# 4. 1 — Purchase Order Management

## 4.1 Objective

The first  implemented the Purchase Order management lifecycle.

The service supports:

* Create Purchase Order
* Get all Purchase Orders
* Get Purchase Order by PO number
* Update Purchase Order
* Delete Purchase Order
* Acknowledge Purchase Order
* Controlled state transitions
* Illegal transition rejection
* Transition history
* Event retrieval
* Actor tracking
* Transition timestamps
* Expected delivery tracking
* Actual delivery tracking
* Duplicate Purchase Order protection

---

# 5. Purchase Order Data Model

A Purchase Order contains:

```text
po_number
supplier_id
items
total_amount
status
created_at
expected_delivery
actual_delivery_date
history
```

A newly created Purchase Order starts in:

```text
draft
```

---

# 6. Purchase Order Lifecycle

```text
                         ┌─────────────┐
                         │  Cancelled  │
                         └─────────────┘
                               ▲
                               │
                               │
Draft ─────────► Sent ─────────► Acknowledged ─────────► Fulfilled
  │                │                  │
  │                │                  │
  └────────────────┴──────────────────┘
             Cancelled
```

The implemented state machine is:

| Current State  | Allowed Transitions         |
| -------------- | --------------------------- |
| `draft`        | `sent`, `cancelled`         |
| `sent`         | `acknowledged`, `cancelled` |
| `acknowledged` | `fulfilled`, `cancelled`    |
| `fulfilled`    | None                        |
| `cancelled`    | None                        |

---

# 7. Purchase Order Transition API

```http
POST /api/v1/purchase-orders/{po_number}/transition
```

Example:

```json
{
    "target_state": "sent",
    "actor": "admin"
}
```

Supplier acknowledgement:

```json
{
    "target_state": "acknowledged",
    "actor": "supplier"
}
```

Fulfilment:

```json
{
    "target_state": "fulfilled",
    "actor": "admin"
}
```

The `actor` field records who performed the transition.

---

# 8. Illegal State Transitions

Illegal transitions return:

```text
HTTP 400
```

For example, this transition is illegal:

```text
draft → acknowledged
```

because the PO must first move to:

```text
draft → sent → acknowledged
```

Example error:

```text
Cannot go from draft to acknowledged.
Allowed: sent, cancelled.
```

A terminal state such as `fulfilled` cannot move backwards:

```text
fulfilled → draft
```

Example:

```text
Cannot go from fulfilled to draft.
Allowed: none.
```

---

# 9. Purchase Order Audit History

Every successful state transition creates an event.

Each event records:

```text
actor
from_status
to_status
timestamp
```

Example:

```json
[
    {
        "actor": "admin",
        "from_status": "draft",
        "to_status": "sent",
        "timestamp": "2026-08-06T10:00:00"
    },
    {
        "actor": "supplier",
        "from_status": "sent",
        "to_status": "acknowledged",
        "timestamp": "2026-08-06T11:00:00"
    },
    {
        "actor": "admin",
        "from_status": "acknowledged",
        "to_status": "fulfilled",
        "timestamp": "2026-08-07T09:00:00"
    }
]
```

---

# 10. Purchase Order Events API

```http
GET /api/v1/purchase-orders/{po_number}/events
```

This endpoint returns the complete transition history for the PO.

The event store acts as the audit source for state changes.

An important implementation decision is that deleting an active Purchase Order does not remove its historical transition events.

This preserves the audit trail.

---

# 11. Actual Delivery Tracking

Fulfilled Purchase Orders contain:

```text
expected_delivery
actual_delivery_date
```

Example:

```json
{
    "expected_delivery": "2026-08-02",
    "actual_delivery_date": "2026-08-01"
}
```

Delivery classification:

```text
actual_delivery_date <= expected_delivery
        │
        ├── YES → On time
        │
        └── NO  → Late
```

---

# 12. — Blockers Encountered in purchade_order

### Blocker 1 — Illegal state transitions

Initially, it was possible to think of the PO lifecycle as simple status updates.

The requirement actually needed a controlled state machine.

### Resolution

Implemented explicit legal transitions:

```text
draft → sent
sent → acknowledged
acknowledged → fulfilled
```

and cancellation paths.

Illegal transitions now return HTTP 400.

---

### Blocker 2 — Transition history did not initially show the complete lifecycle

During testing, the history appeared to contain only later transitions instead of the complete sequence.

### Resolution

Transition events were explicitly stored whenever a legal transition occurred.

Each event records:

```text
from_status
to_status
actor
timestamp
```

---

### Blocker 3 — Confusion about where history should be exposed

The history initially existed internally, but it was unclear whether it should be visible through an API.

### Resolution

A dedicated events endpoint was implemented:

```http
GET /api/v1/purchase-orders/{po_number}/events
```

This makes the audit history observable through Swagger and API clients.

---

### Blocker 4 — Delivery performance required actual delivery information

Expected delivery alone cannot determine whether a supplier delivered on time.

### Resolution

Added:

```text
actual_delivery_date
```

and used:

```text
actual_delivery_date <= expected_delivery
```

to determine on-time delivery.

---

# 13. 2 — Invoice Management

## 13.1 Objective

The second we implemented the complete Invoice Management functionality for the Supplier Portal Service.

The objective was to allow suppliers and procurement users to:

* Create and retrieve invoices
* Validate invoice information
* Validate the Purchase Order associated with an invoice
* Validate supplier information
* Validate invoice amounts against PO amounts
* Prevent duplicate invoices
* Manage the invoice lifecycle
* Handle disputed invoices
* Resolve invoice disputes
* Upload invoice PDF documents
* Validate uploaded PDF documents
* Download stored invoice documents securely
* Protect invoice document storage from path traversal
* Test legal and illegal invoice scenarios

The implementation builds on the Purchase Order lifecycle implemented.

The overall relationship is:

```text
Purchase Order
      │
      ▼
Acknowledged / Fulfilled
      │
      ▼
Invoice Created
      │
      ▼
Submitted
      │
      ├──────────────► Disputed
      │                    │
      │                    ▼
      │                 Resolved
      │                    │
      │                    ▼
      └────────────────► Approved
```

---

# 14. Invoice Data Model

An Invoice contains the following information:

```text
invoice_number
po_number
supplier_id
amount
invoice_date
document_url
status
dispute
```

Example:

```json
{
    "invoice_number": "INV1001",
    "po_number": "PO1001",
    "supplier_id": "SUP001",
    "amount": 50000,
    "invoice_date": "2026-08-06",
    "document_url": null,
    "status": "submitted",
    "dispute": null
}
```

The invoice number uniquely identifies the invoice within the supplier context.

---

# 15. Invoice Lifecycle

The invoice lifecycle was implemented as a controlled state machine.

```text

                    
 Submitted
   │
   ├──────────────► Approved
   │
   ├──────────────► Rejected
   │
   ▼
Disputed
   │
   ├──────────────► Approved
   ├──────────────► Rejected
   └──────────────► Adjusted
                         │
                         ├────────► Approved
                         └────────► Rejected
```

The important business states are:

```text
submitted
disputed
adjusted
approved
rejected
```

---

# 16. Invoice State Transition Rules

Invoice status changes are controlled rather than allowing arbitrary status updates.

The intended lifecycle is:

Current Status	Allowed Status
Submitted	    Approved, Disputed, Rejected
Disputed	    Approved, Rejected, Adjusted
Adjusted	    Approved, Rejected
Approved	    None
Rejected	    None


---

# 17. Legal Invoice Transitions

The following transitions are legal:

```text
Submitted → Approved
Submitted → Disputed
Submitted → Rejected

Disputed → Approved
Disputed → Rejected
Disputed → Adjusted

Adjusted → Approved
Adjusted → Rejected
```

Each legal transition represents a valid business event.

For example:

```json
{
    "target_state": "submitted",
    "actor": "supplier"
}
```

and:

```json
{
    "target_state": "disputed",
    "actor": "admin"
}
```

---

# 18. Illegal Invoice Transitions

The service rejects transitions that do not follow the defined invoice lifecycle.

Examples:

```text
Submitted → Submitted
Submitted → Adjusted

Approved → Submitted
Approved → Disputed
Approved → Rejected
Approved → Adjusted
Approved → Approved

Disputed → Submitted
Disputed → Disputed

Rejected → Submitted
Rejected → Disputed
Rejected → Approved
Rejected → Adjusted
Rejected → Rejected

Adjusted → Submitted
Adjusted → Disputed
Adjusted → Adjusted
```

Illegal transitions return:

```http
400 Bad Request
```

Example:

```json
{
    "detail": "Cannot transition invoice from Rejected to approved."
}
```

This prevents an invoice from bypassing required business states.

---

# 19. Invoice Transition Validation

Every invoice transition is validated before changing the status.

The transition process is conceptually:

```text
Request
   │
   ▼
Find Invoice
   │
   ▼
Validate Target Status
   │
   ▼
Check Current → Target Transition
   │
   ├── Invalid ──► HTTP 400
   │
   ▼
Apply Transition
   │
   ▼
Store New Status
```

The service therefore does not directly trust the requested target state.

---

# 20. Invoice Creation / Submission

An invoice can only be created when the referenced Purchase Order satisfies the invoice business rules.

The creation process validates:

```text
Invoice Number
      │
Supplier ID
      │
Purchase Order
      │
Purchase Order Status
      │
Invoice Amount
      │
Duplicate Invoice
      │
      ▼
Create Invoice
```

The invoice cannot bypass these validations.

---

# 21. Purchase Order Validation

An invoice must reference an existing Purchase Order.

Example:

```text
Invoice PO Number = PO1001
```

The service searches the Purchase Order store.

If the PO does not exist:

```text
Purchase Order not found.
```

is returned.

Example:

```http
404 Not Found
```

This prevents orphan invoices from being created.

---

# 22. Purchase Order Status Validation

Invoice creation is restricted based on the Purchase Order lifecycle.

Invoices are allowed only when the Purchase Order has reached:

```text
acknowledged
fulfilled
```

Invoices are rejected when the PO is still:

```text
draft
sent
```

Therefore:

```text
Draft
  │
  X ── Invoice not allowed

Sent
  │
  X ── Invoice not allowed

Acknowledged
  │
  ▼
Invoice allowed

Fulfilled
  │
  ▼
Invoice allowed
```

This ensures that suppliers cannot submit invoices against POs that have not reached the required procurement stage.

---

# 23. Invoice Number Validation

Invoice numbers are validated using:

```regex
^[A-Za-z0-9_-]+$
```

Valid examples:

```text
INV1001
INV-1001
INV_1001
```

Invalid examples include values containing unsupported characters:

```text
INV/1001
INV 1001
INV@1001
INV#1001
```

These values are rejected at the schema-validation layer.

This validation is also important because invoice numbers are used when constructing document paths.

---

# 24. Supplier ID Validation

Supplier IDs use the same validation pattern:

```regex
^[A-Za-z0-9_-]+$
```

Valid examples:

```text
SUP001
SUP-001
SUP_001
```

Invalid examples include:

```text
SUP/001
SUP 001
SUP@001
SUP..001
```

Supplier ID validation is particularly important because the supplier ID participates in the invoice document directory structure.

---

# 25. Invoice Amount Validation

The invoice amount is validated against the corresponding Purchase Order amount.

The service uses a centralized tolerance:

```python
TOLERANCE = 0.05
```

The permitted range is:

```text
minimum_amount = po_amount × (1 - TOLERANCE)

maximum_amount = po_amount × (1 + TOLERANCE)
```

Therefore:

```text
95% ≤ Invoice Amount ≤ 105%
```

is accepted.

---

# 26. Invoice Amount Boundary Cases

For a Purchase Order amount of:

```text
1000
```

the permitted range is:

```text
Minimum = 1000 × 0.95
        = 950

Maximum = 1000 × 1.05
        = 1050
```

Therefore:

| Invoice Amount | Result   |
| -------------: | -------- |
|            949 | Rejected |
|            950 | Accepted |
|            951 | Accepted |
|           1000 | Accepted |
|           1049 | Accepted |
|           1050 | Accepted |
|           1051 | Rejected |

The exact tolerance boundaries are therefore valid.

---

# 27. Duplicate Invoice Protection

Duplicate invoices are prevented using the combination of:

```text
invoice_number
supplier_id
```

For example:

```text
Supplier = SUP001
Invoice   = INV1001
```

If the same supplier attempts to create:

```text
SUP001 + INV1001
```

again, the service rejects the request.

This prevents duplicate invoice submissions.

A different supplier may use the same invoice number because the uniqueness rule is supplier-specific.

---

# 28. Invoice Dispute Management

Invoices can enter a dispute state when an invoice requires investigation or correction.

The lifecycle is:

```text
Submitted
    │
    ▼
Disputed
    │
    ▼
Resolved
    │
    ▼
Approved
```

A dispute can contain information such as:

```json
{
    "reason": "Incorrect price",
    "description": "Invoice amount does not match agreed pricing."
}
```

The existence of dispute information is also used by supplier performance calculations.

---

# 29. Invoice Resolution

Once a disputed invoice has been investigated, it can be resolved through one of the following outcomes:

Disputed → Approved
Disputed → Rejected
Disputed → Adjusted

An Adjusted invoice represents an invoice whose line items or invoice details have been corrected after the dispute.

An adjusted invoice can then proceed to:

Adjusted → Approved
Adjusted → Rejected

Therefore, the dispute resolution flow is:

Disputed
   │
   ├──────────────► Approved
   │
   ├──────────────► Rejected
   │
   └──────────────► Adjusted
                         │
                         ├────────► Approved
                         └────────► Rejected

# 30. Invoice Dispute History

For supplier performance measurement, an invoice that has entered the dispute process remains historically disputed.

The implementation determines this using:

```python
invoice.get("dispute") is not None
```

Therefore:

```text
Submitted
   ↓
Disputed
   ↓
Resolved
   ↓
Approved
```

does not erase the historical fact that the invoice was disputed.

This is important for supplier accuracy and dispute-rate calculations.

---

# 31. Invoice Transition Audit Information

Where transition history is implemented, each invoice state change should capture:

```text
actor
previous status
new status
timestamp
```

Example:

```json
{
    "actor": "supplier",
    "from_status": "created",
    "to_status": "submitted",
    "timestamp": "2026-08-06T10:00:00"
}
```

This provides an audit trail for invoice lifecycle activity.

If transition history is not yet persisted separately in the current implementation, the README should treat this as a future audit enhancement rather than claiming it is already implemented.

---

# 32. Invoice APIs

The invoice management endpoints include:

| Method | Endpoint                                     | Description          |
| ------ | -------------------------------------------- | -------------------- |
| GET    | `/api/v1/invoices`                           | Retrieve invoices    |
| POST   | `/api/v1/invoices`                           | Create invoice       |
| POST   | `/api/v1/invoices/{invoice_number}/document` | Upload invoice PDF   |
| GET    | `/api/v1/invoices/{invoice_number}/document` | Download invoice PDF |

The invoice lifecycle transition endpoint, if exposed separately by the implementation, follows the same controlled state-machine rules described above.

---

# 33. Invoice PDF Upload

Invoice documents are uploaded through:

```http
POST /api/v1/invoices/{invoice_number}/document
```

Only PDF documents are accepted.

The expected content type is:

```text
application/pdf
```

The upload process performs multiple security checks before storing the file.

---

# 34. PDF Content-Type Validation

The HTTP Content-Type must be:

```text
application/pdf
```

Requests with other content types are rejected.

For example:

```text
text/plain
image/png
application/json
```

are not accepted as invoice documents.

However, Content-Type alone is not considered sufficient validation.

---

# 35. PDF Signature Validation

The service also validates the actual file content.

A valid PDF must begin with:

```text
%PDF-
```

This prevents a malicious or incorrect file from being accepted simply because the HTTP request declares:

```text
Content-Type: application/pdf
```

The implementation therefore checks:

```text
HTTP Content-Type
        +
Actual PDF Signature
```

before accepting the document.

---

# 36. Invoice PDF Size Validation

The maximum invoice document size is:

```text
10 MB
```

The service validates the upload size before processing when file metadata is available and also validates the actual bytes after reading the file.

This protects the service from oversized invoice uploads.

---

# 37. Invoice Document Storage

Documents are stored using the supplier ID as part of the directory structure.

Conceptually:

```text
uploads/
└── SUP001/
    └── INV1001.pdf
```

The resulting path is stored against the invoice using:

```text
document_url
```

The document therefore remains associated with the corresponding invoice.

---

# 38. Invoice Path Traversal Protection

Invoice documents require special filesystem protection because supplier and invoice values participate in document paths.

The upload root is resolved:

```python
upload_root = Path(UPLOAD_DIR).resolve()
```

The final path is also resolved:

```python
final_path = ...
```

The implementation then verifies:

```python
if not final_path.is_relative_to(upload_root):
    raise ValueError("Invalid file path.")
```

This ensures the final file remains inside the configured upload directory.

This is safer than using:

```python
final_path.startswith(upload_root)
```

because filesystem paths must be compared structurally rather than as plain strings.

---

# 39. Invoice Document Download

Invoice documents can be retrieved through:

```http
GET /api/v1/invoices/{invoice_number}/document
```

The service verifies:

```text
Invoice exists
       │
       ▼
Document path exists
       │
       ▼
Stored file exists
       │
       ▼
Return PDF
```

The document is returned as a file response rather than a JSON representation of the file.

---

# 40. File Response Implementation

One implementation issue encountered during this was the distinction between returning a normal response and returning an actual document.

The invoice document download endpoint needs to return the stored PDF itself.

Therefore the implementation uses FastAPI's file-response mechanism.

Conceptually:

```text
Stored PDF
    │
    ▼
FileResponse
    │
    ▼
Client receives PDF
```

This is appropriate for document-download APIs because the client receives the actual file rather than JSON containing file contents.

---

# 41. Invoice Validation Architecture

Invoice validation is divided into two layers.

### Schema-Level Validation

Pydantic validates structural input such as:

```text
invoice_number
supplier_id
amount
invoice_date
```

Examples:

```text
Invalid invoice number
Invalid supplier ID
Invalid field type
Invalid numeric constraints
```

### Service-Level Validation

Business rules are validated by the invoice service:

```text
PO existence
PO status
Invoice amount tolerance
Duplicate invoice
Invoice lifecycle
Document rules
```

This separation keeps data validation and business logic independent.

---

# 42. Invoice Creation Flow

The complete invoice creation process is:

```text
Client
  │
  ▼
POST /api/v1/invoices
  │
  ▼
Pydantic Validation
  │
  ├── Invoice Number
  ├── Supplier ID
  └── Amount / Fields
  │
  ▼
Service Validation
  │
  ├── PO Exists?
  ├── PO Status Valid?
  ├── Amount Within Tolerance?
  └── Duplicate Invoice?
  │
  ├── Failure ──► HTTP Error
  │
  ▼
Invoice Created
  │
  ▼
Invoice Status
```

---

# 43. Invoice Document Flow

The document flow is:

```text
Invoice Created
      │
      ▼
PDF Upload
      │
      ▼
Content-Type Validation
      │
      ▼
PDF Signature Validation
      │
      ▼
File Size Validation
      │
      ▼
Safe Path Validation
      │
      ▼
Create Supplier Directory
      │
      ▼
Store PDF
      │
      ▼
Save document_url
```

---

# 44. Orphaned Invoice Files


The invoice service provides a mechanism to identify invoice PDF files that
are no longer properly associated with an active invoice record.


An invoice PDF is considered orphaned when:


1. The file is a PDF inside the invoice upload directory.
2. The file is older than the configured `older_than_days` threshold.
3. The corresponding invoice record does not exist, or the invoice exists but
   the file is not considered validly associated with a completed invoice.


The default threshold is:


```text
older_than_days = 1

This means files that are less than one day old are not considered orphaned.

## 44.1 Invoice Terminal States

The following invoice states are considered terminal:

Approved
Rejected

Files belonging to invoices in these states are protected and are not
considered orphaned.

The following states are non-terminal:

Submitted
Disputed
Adjusted

Files associated with invoices in these states can be considered orphaned
when they exceed the configured age threshold.

## 44.2 Orphan Detection Rules


The service checks invoice PDF files under supplier-specific directories:

uploads/
├── SUP001/
│   ├── INV1001.pdf
│   └── INV1002.pdf
├── SUP002/
│   └── INV2001.pdf

The supplier ID and invoice number are used together to identify the
corresponding invoice:

(supplier_id, invoice_number)

For example:

SUP001/INV1001.pdf

is associated with:

("SUP001", "INV1001")


44.3 Cases Considered Orphaned

Case 1: Invoice Record Does Not Exist

If an old PDF file exists but there is no corresponding invoice record, the
file is considered orphaned.

PDF file exists
      │
      ▼
Invoice record does not exist
      │
      ▼
ORPHANED

The result includes:

reason:
"No matching invoice record exists."
Case 2: Invoice Is Non-Terminal and Document Is Not Registered

If the invoice exists but:

document_url = None

the physical PDF file has no registered association with the invoice.

The file is therefore considered orphaned if it is older than the configured
threshold.

Invoice exists
      │
      ▼
Non-terminal status
      │
      ▼
document_url missing
      │
      ▼
ORPHANED
Case 3: Stored Document Path Does Not Match

If the invoice has a document_url, but the stored path does not match the
actual PDF file being scanned, the file is considered orphaned.

For example:

Actual file:
uploads/SUP001/INV1001.pdf


Invoice document_url:
uploads/SUP001/different-file.pdf

The file is reported with:

reason:
"File path does not match the invoice document."
Case 4: Non-Terminal Invoice With an Old Registered File

If:

the invoice exists,
the invoice is non-terminal,
the document is correctly registered,
and the file is older than the configured threshold,

the file is still considered orphaned because the invoice has remained
incomplete beyond the configured age threshold.

Non-terminal invoice
        │
        ▼
Correct document association
        │
        ▼
File older than threshold
        │
        ▼
ORPHANED


30.4 Recent Files Are Protected

Files newer than the configured threshold are ignored.

For example, with:

older_than_days = 1

a recently uploaded invoice PDF is not considered orphaned.

File age < 1 day
      │
      ▼
NOT ORPHANED

This prevents recently uploaded invoice documents from being incorrectly
identified or deleted.

44.5 Finding Orphaned Files

The service provides:

find_orphaned_invoice_files(
    older_than_days=1
)

The function scans the invoice upload directory and returns information about
files identified as orphaned.

Each result can contain:

invoice_number
supplier_id
file_path
file_name
size_bytes
invoice_status
file_age_days
reason

Example:

{
    "invoice_number": "INV1001",
    "supplier_id": "SUP001",
    "file_name": "INV1001.pdf",
    "invoice_status": "submitted",
    "file_age_days": 2.0,
    "reason": "Invoice is not in a terminal state and has remained incomplete beyond the configured age threshold."
}

If the upload directory does not exist, the function returns an empty list.

A negative older_than_days value is rejected.


44.5. Purging Orphaned Invoice Files
-----------------------------------------------------------------------------

The invoice service also provides a purge operation that physically deletes
files identified as orphaned.

The function is:

purge_orphaned_invoice_files(
    older_than_days=1
)

The purge operation first calls:

find_orphaned_invoice_files()

and deletes only the files returned by the orphan-detection process.

44.6 Purge Flow

The purge process is:

Find PDF files
      │
      ▼
Check file age
      │
      ▼
Ignore recent files
      │
      ▼
Find matching invoice
      │
      ▼
Check invoice status
      │
      ├──────────────► Approved / Rejected
      │                      │
      │                      ▼
      │                   KEEP FILE
      │
      ▼
Check document association
      │
      ▼
Identify orphan
      │
      ▼
Delete file
31.2 Terminal Invoice Files Are Never Deleted

Files belonging to completed invoices are protected.

Approved → KEEP
Rejected → KEEP

Therefore:

Old approved invoice PDF → KEEP
Old rejected invoice PDF → KEEP

The purge operation only deletes files identified as orphaned.

44.7 Recent Orphan Files Are Not Deleted

Even if a file does not have a matching invoice record, it will not be deleted
if it is newer than the configured threshold.

For example:

Recent orphan PDF
      │
      ▼
Below age threshold
      │
      ▼
KEEP

This provides protection against deleting files that may have been uploaded
recently but have not yet been associated with an invoice record.

44.8 Purge Result

The purge operation returns:

{
    "total": 3,
    "deleted": 3,
    "files": [],
    "older_than_days": 1
}

The result contains:

Field	Description
total	Total number of orphaned files identified
deleted	Number of files successfully deleted
files	Details of files successfully deleted
older_than_days	Age threshold used for the purge

If one file cannot be deleted, the service continues processing the remaining
orphaned files.

44.9 Safety Rules

The orphan-file cleanup process follows these rules:

Recent file              → KEEP
Approved invoice         → KEEP
Rejected invoice         → KEEP
Old orphaned file        → DELETE

The cleanup process therefore avoids deleting:

Recently uploaded PDFs
Approved invoice documents
Rejected invoice documents

Only files identified by the orphan-detection logic are eligible for
deletion.

# . Blockers Encountered 
-----------------------------

## Blocker 1 — Invoice Validation Was Not a Simple CRUD Operation

The invoice initially appeared to be a straightforward resource:

```text
Create Invoice
Retrieve Invoice
```

However, creation depended on multiple business conditions.

The invoice needed to validate:

```text
Invoice Number
Supplier ID
PO Existence
PO Status
Invoice Amount
Duplicate Invoice
```

### Resolution

Validation was separated into:

```text
Schema Validation
        +
Service Business Validation
```

This made the invoice implementation easier to maintain and test.

---

 ## Blocker 2 — Invoice Amount Tolerance

One of the most important business rules was the invoice amount tolerance.

The implementation needed to determine whether exact boundary values were valid.

For a PO amount of 1000:

```text
950
1050
```

had to be tested carefully.

### Resolution

The tolerance was centralized:

```python
TOLERANCE = 0.05
```

and the allowed range was calculated dynamically:

```text
minimum_amount = po_amount * (1 - TOLERANCE)
maximum_amount = po_amount * (1 + TOLERANCE)
```

This avoided hard-coding `950` or `1050`.

---

## Blocker 3 — Boundary Testing

The tolerance requirement created four important boundary cases:

```text
949  → Reject
950  → Accept
1050 → Accept
1051 → Reject
```

These tests were necessary because a small comparison mistake such as:

```text
<
```

instead of:

```text
<=
```

would incorrectly reject a valid boundary invoice.

---

## Blocker 4 — Purchase Order Status Dependency

Invoice creation depends on the PO lifecycle.

The service needed to prevent invoices from being created against:

```text
draft
sent
```

while allowing:

```text
acknowledged
fulfilled
```

### Resolution

The invoice service checks the current Purchase Order status before creating the invoice.

This connects  directly to the Purchase Order state machine implemented in.

---

## Blocker 5 — Invoice Lifecycle Transitions

Invoice states could not be treated as arbitrary string values.

For example:

```text
Created → Approved
```

would bypass the required submission process.

Similarly:

```text
Disputed → Approved
```

would bypass dispute resolution.

### Resolution

A controlled invoice state machine was defined:

```text
Created → Submitted
Submitted → Approved
Submitted → Disputed
Disputed → Resolved
Resolved → Approved
```

Illegal transitions return:

```http
400 Bad Request
```

---

## Blocker 6 — Dispute History

A resolved dispute should not disappear from supplier performance history.

For example:

```text
Submitted
    ↓
Disputed
    ↓
Resolved
    ↓
Approved
```

The invoice is still historically disputed.

### Resolution

The supplier scorecard identifies historical disputes through the dispute information associated with the invoice.

---

## Blocker 7 — PDF Content-Type Was Not Enough

An uploaded file could claim:

```text
application/pdf
```

without actually being a PDF.

### Resolution

Two validations were introduced:

```text
Content-Type = application/pdf
```

and:

```text
File starts with %PDF-
```

This provides a stronger document-validation mechanism.

---

## Blocker 8 — PDF File Size

The service needed to enforce:

```text
Maximum = 10 MB
```

Checking only the metadata was not sufficient.

### Resolution

The service validates the actual uploaded file bytes after reading them.

This ensures the real payload does not exceed the configured limit.

---

## Blocker 9 — Path Traversal

Invoice documents use supplier and invoice information when constructing filesystem paths.

An unsafe path could potentially attempt to escape the upload directory.

For example:

```text
../../some-file
```

could be dangerous if not handled correctly.

### Resolution

The implementation resolves both the upload root and final file path:

```python
upload_root = Path(UPLOAD_DIR).resolve()
```

and:

```python
final_path = final_path.resolve()
```

Then:

```python
if not final_path.is_relative_to(upload_root):
    raise ValueError("Invalid file path.")
```

The directory is created only after the path has passed this security check.

---

## Blocker 10 — Safe Filename Handling

Invoice numbers are used when generating document filenames.

Because invoice numbers originate from external input, unrestricted characters could create unsafe filesystem paths.

### Resolution

Invoice number validation was performed before using the value in document storage.

The allowed pattern is:

```regex
^[A-Za-z0-9_-]+$
```

This provides predictable document names such as:

```text
INV1001.pdf
INV-1001.pdf
INV_1001.pdf
```

---

## Blocker 11 — File Download Response

The document-download endpoint originally required clarification about whether the stored file should be returned as JSON or as an actual file.

### Resolution

The endpoint returns the stored PDF using a file-response mechanism.

This allows browsers and API clients to receive the actual invoice document.

---

## Blocker 12 — Missing or Invalid Stored Documents

An invoice may exist while its document does not.

The download operation therefore needs to distinguish between:

```text
Invoice does not exist
Document path missing
File missing
```

### Resolution

The document-download flow validates the invoice and stored document before returning the file.

---

## Blocker 13 — Supplier ID and Filesystem Security

Supplier IDs are not only business identifiers.

They are also used to construct document directories:

```text
uploads/SUP001/
```

Therefore allowing arbitrary supplier ID characters could introduce filesystem risks.

### Resolution

Supplier IDs are restricted to:

```regex
^[A-Za-z0-9_-]+$
```

before they reach document-storage logic.

---

## Blocker 14 — Duplicate Invoice Semantics

A duplicate invoice should be detected within the supplier context.

For example:

```text
SUP001 + INV1001
```

must not be created twice.

However:

```text
SUP002 + INV1001
```

may represent a different supplier's invoice.

### Resolution

Duplicate validation uses:

```text
invoice_number + supplier_id
```

rather than invoice number alone.

---

## Blocker 15 — Invoice Lifecycle and Validation Interaction

A transition cannot be performed without considering the invoice's current business state.

For example:

```text
Submitted → Disputed
```

is valid.

But:

```text
Created → Disputed
```

must be rejected.

### Resolution

The transition service checks the current status and compares it against the allowed transition map before changing the invoice status.

---

## Blocker 16 — Testing Legal and Illegal Transitions

Testing only successful invoice transitions was insufficient.

Every legal state transition needed to be tested alongside invalid transitions.

### Legal Transition Tests

```text
Created → Submitted
Submitted → Approved
Submitted → Disputed
Disputed → Resolved
Resolved → Approved
```

### Illegal Transition Tests

```text
Created → Approved
Created → Disputed
Submitted → Resolved
Disputed → Approved
Approved → Submitted
Approved → Disputed
Approved → Created
Resolved → Submitted
```

Every illegal transition must return:

```http
400 Bad Request
```

---

## Blocker 17 — Invoice Validation During Transitions

The transition operation must not blindly update the invoice dictionary.

Before applying the transition, the service must determine:

```text
Invoice exists?
       │
       ▼
Current status valid?
       │
       ▼
Target status allowed?
       │
       ▼
Transition permitted?
       │
       ▼
Update invoice
```

This prevents corrupted lifecycle states.

---

## Blocker 18 — Schema Validation vs Business Validation

Another implementation distinction was identifying which checks belong in Pydantic schemas and which belong in services.

### Schema

Used for:

```text
Data type
Required fields
Regex
Numeric constraints
Percentage constraints
```

### Service

Used for:

```text
PO existence
PO status
Duplicate invoice
Amount tolerance
Lifecycle transitions
File validation
Filesystem security
```

This separation prevents business logic from being placed incorrectly inside request schemas.

---

## Blocker 19 — End-to-End Invoice Testing

The final blocker was ensuring that invoice functionality worked across the entire flow rather than testing individual functions only.

The complete flow needed to work as:

```text
Purchase Order
      │
      ▼
Acknowledged / Fulfilled
      │
      ▼
Create Invoice
      │
      ▼
Submit Invoice
      │
      ├────────► Dispute
      │             │
      │             ▼
      │          Resolve
      │             │
      └─────────────┴──► Approve
                           │
                           ▼
                     Upload PDF
                           │
                           ▼
                     Download PDF
```

The test suite therefore validates both individual business rules and API-level behavior.

---

# 45. Test Coverage

The invoice test suite covers the following areas.

## Invoice Creation

```text
✓ Create valid invoice
✓ Retrieve invoices
✓ Retrieve invoice data
✓ Invalid invoice number
✓ Invalid supplier ID
✓ Missing Purchase Order
✓ Invalid Purchase Order status
✓ Duplicate invoice
```

## Invoice Amount

```text
✓ Amount below tolerance rejected
✓ Exact 95% boundary accepted
✓ Amount within tolerance accepted
✓ Exact PO amount accepted
✓ Exact 105% boundary accepted
✓ Amount above tolerance rejected
```

## Invoice Lifecycle

```text
✓ Created → Submitted
✓ Submitted → Approved
✓ Submitted → Disputed
✓ Disputed → Resolved
✓ Resolved → Approved
```

## Illegal Lifecycle Transitions

```text
✓ Created → Approved rejected
✓ Created → Disputed rejected
✓ Submitted → Resolved rejected
✓ Disputed → Approved rejected
✓ Approved → Submitted rejected
✓ Approved → Disputed rejected
✓ Approved → Created rejected
✓ Resolved → Submitted rejected
```

## PDF Upload

```text
✓ Valid PDF accepted
✓ Wrong Content-Type rejected
✓ Invalid PDF signature rejected
✓ File larger than 10 MB rejected
✓ Valid PDF stored
✓ document_url updated
```

## PDF Download

```text
✓ Existing document downloaded
✓ Unknown invoice rejected
✓ Missing document rejected
✓ Missing stored file rejected
```

## Security

```text
✓ Supplier ID validation
✓ Invoice number validation
✓ Safe filename validation
✓ Path traversal protection
```

---

# 46.  Final Implementation

At the completion invoice, the Invoice Management service provides:

```text
Invoice Management
│
├── Invoice Creation
│   ├── Invoice validation
│   ├── Supplier validation
│   ├── PO validation
│   ├── PO status validation
│   ├── Amount tolerance
│   └── Duplicate protection
│
├── Invoice Lifecycle
│   ├── Created
│   ├── Submitted
│   ├── Disputed
│   ├── Resolved
│   └── Approved
│
├── Invoice Documents
│   ├── PDF upload
│   ├── Content-Type validation
│   ├── PDF signature validation
│   ├── 10 MB size validation
│   ├── Secure storage
│   └── PDF download
│
├── Security
│   ├── Supplier ID validation
│   ├── Invoice number validation
│   ├── Safe path handling
│   └── Path traversal protection
│
└── Testing
    ├── Creation tests
    ├── Validation tests
    ├── Boundary tests
    ├── Transition tests
    ├── PDF tests
    └── Security tests
```

 therefore extends the Purchase Order functionality from po into a complete invoice-processing workflow while enforcing business validation, lifecycle control, document security, and automated testing.

# 47. 3 — Supplier Statistics

## 47.1 Objective

The third implementation stage introduced operational supplier statistics for monitoring supplier performance.

The service provides the following supplier-level metrics:

* Purchase Order count
* On-time delivery percentage
* Average invoice cycle time
* Supplier not-found handling
* Date normalization
* Missing-data handling

### Endpoint

```http
GET /api/v1/suppliers/{supplier_id}/stats
```

The endpoint calculates the metrics directly from the current in-memory Purchase Order and Invoice stores.

---

# 48. Supplier Purchase Order Count

The Purchase Order count represents the total number of Purchase Orders belonging to the requested supplier.

```text
po_count = total supplier purchase orders
```

For example:

```text
SUP001

PO1001
PO1002
PO1003
```

The resulting count is:

```text
po_count = 3
```

Both fulfilled and unfulfilled Purchase Orders are included in the total count.

---

# 49. On-Time Delivery Percentage

The implementation follows the required business definition:

```text
on-time delivery percentage =
(on-time purchase orders / total supplier purchase orders) × 100
```

A Purchase Order is considered on time when:

```text
actual_delivery_date <= expected_delivery
```

Therefore:

* Delivery before the expected date → On time
* Delivery exactly on the expected date → On time
* Delivery after the expected date → Late

### Example

| Purchase Order | Expected Delivery | Actual Delivery | Result  |
| -------------- | ----------------- | --------------- | ------- |
| PO1001         | 2026-08-02        | 2026-08-01      | On time |
| PO1002         | 2026-08-03        | 2026-08-04      | Late    |
| PO1003         | 2026-08-05        | 2026-08-05      | On time |

Therefore:

```text
On-time POs = 2
Total POs = 3

(2 / 3) × 100 = 66.67%
```

The implementation rounds the result to two decimal places.

---

# 50. Unfulfilled Purchase Orders

Unfulfilled Purchase Orders remain part of the total Purchase Order count.

For example:

```text
PO1001 → fulfilled → on time
PO1002 → acknowledged → no delivery outcome
```

The denominator remains:

```text
Total POs = 2
```

Only Purchase Orders with an actual delivery outcome can contribute to the on-time count.

This distinction was important because the original calculation could incorrectly use only fulfilled Purchase Orders as the denominator.

The implemented business rule is:

```text
on-time POs / total supplier POs × 100
```

---

# 51. Missing Delivery Information

A fulfilled Purchase Order may not contain both delivery dates.

The implementation checks:

```text
expected_delivery
actual_delivery_date
```

If either value is missing:

```text
expected_delivery = None
```

or:

```text
actual_delivery_date = None
```

the Purchase Order is not counted as an on-time delivery.

The incomplete record does not cause the entire supplier statistics request to fail.

---

# 52. Average Invoice Cycle Time

The service also calculates the average time between Purchase Order creation and invoice creation.

The formula is:

```text
invoice cycle time =
invoice date - Purchase Order creation date
```

### Example

| PO Created | Invoice Date | Cycle Time |
| ---------- | ------------ | ---------: |
| July 20    | July 23      |     3 days |
| July 22    | July 26      |     4 days |

Average:

```text
(3 + 4) / 2 = 3.5 days
```

The API returns:

```json
{
    "average_invoice_cycle_time": 3.5
}
```

---

# 53. Invalid and Negative Cycle Times

The implementation protects the KPI from invalid invoice records.

Negative cycle times are ignored.

For example:

```text
PO created:     August 10
Invoice date:   August 08
```

would result in:

```text
cycle_days = -2
```

This record is excluded because a negative invoice cycle time would corrupt the supplier KPI.

Invalid date values are also ignored rather than causing the complete statistics calculation to fail.

---

# 54. Date Normalization

Supplier statistics can receive dates in several formats.

Supported values include:

```text
date
datetime
ISO date string
ISO datetime string
ISO datetime with Z
```

Examples:

```text
2026-08-10

2026-08-06T10:00:00

2026-08-06T10:00:00Z
```

A shared helper normalizes these values before calculations:

```python
_to_date(value)
```

The helper converts supported values into a Python `date` object.

This keeps delivery and invoice-cycle calculations consistent regardless of the original date representation.

---

# 55. Supplier Not Found Handling

If the requested supplier does not exist in the Purchase Order data, the service raises:

```text
Supplier 'SUP999' not found.
```

The route converts this business exception into:

```http
404 Not Found
```

Example:

```http
GET /api/v1/suppliers/SUP999/stats
```

Response:

```json
{
    "detail": "Supplier 'SUP999' not found."
}
```

---

# 56. Supplier Statistics Response

A successful response follows the `SupplierStatsResponse` schema.

Example:

```json
{
    "supplier_id": "SUP001",
    "po_count": 2,
    "on_time_percentage": 50.0,
    "average_invoice_cycle_time": 3.0
}
```

The response schema validates:

```text
po_count >= 0
0 <= on_time_percentage <= 100
average_invoice_cycle_time >= 0
```

---

# 57. 3 — Blockers Encountered

## Blocker 1 — Incorrect denominator for on-time percentage

The initial calculation considered fulfilled Purchase Orders as the denominator.

The required business rule was:

```text
on-time POs / total supplier POs × 100
```

### Resolution

The calculation was changed to use the complete supplier Purchase Order count:

```python
on_time_percentage = round(
    (on_time_count / total_po_count) * 100,
    2,
)
```

This ensures unfulfilled Purchase Orders remain part of the denominator.

---

## Blocker 2 — Missing actual delivery date

Some fulfilled Purchase Orders did not contain:

```text
actual_delivery_date
```

Without an actual delivery date, delivery performance cannot be evaluated.

### Resolution

Records with missing delivery information are skipped instead of being incorrectly classified as on time.

---

## Blocker 3 — Delivery on the expected date

A boundary case needed to be defined:

```text
actual_delivery_date == expected_delivery
```

### Resolution

The business rule was implemented as:

```python
actual_delivery <= expected_delivery
```

Therefore, delivery exactly on the expected date is considered on time.

---

## Blocker 4 — Mixed date representations

The in-memory data could contain:

```text
date
datetime
string
```

Direct comparison between different date types could cause inconsistent calculations.

### Resolution

A shared `_to_date()` helper was introduced to normalize supported date representations.

---

## Blocker 5 — Invalid invoice dates

Invalid invoice date records could potentially break the complete supplier statistics endpoint.

### Resolution

Date conversion is protected with error handling. Invalid records are ignored while valid supplier records continue to contribute to the KPI.

---

## Blocker 6 — Negative invoice cycle time

A negative difference between invoice date and PO creation date is not a meaningful operational KPI.

### Resolution

Only:

```text
cycle_days >= 0
```

values are included in the average.

---

## Blocker 7 — Supplier statistics endpoint returned 404

The statistics service was implemented correctly, but API tests initially returned:

```text
404 Not Found
```

instead of the expected supplier-specific response.

### Resolution

The supplier statistics router was correctly registered in `main.py`.

---

## Blocker 8 — Circular router registration

During route registration, the application produced:

```text
AttributeError:
partially initialized module
'app.routes.supplier_stats_routes'
has no attribute 'router'
```

The issue occurred because the route module referenced `supplier_stats_routes.router` while the same module was still being initialized.

### Resolution

The route module defines its own router:

```python
router = APIRouter()
```

`main.py` is responsible for registering that router with the FastAPI application.

This separated:

```text
Router definition
```

from:

```text
Application router registration
```

and removed the circular reference.

---

# 58. 3 — Testing Coverage

The supplier statistics implementation was tested at the API, service, and schema levels.

Tests cover:

* Supplier statistics endpoint
* Supplier not found
* Purchase Order count
* All Purchase Orders on time
* No Purchase Orders on time
* Mixed on-time and late deliveries
* Unfulfilled Purchase Orders included in total
* Delivery exactly on expected date
* Missing delivery date
* Average invoice cycle time
* Date normalization
* Invalid dates
* Negative cycle times
* Response schema validation
* Percentage boundaries

The statistics test suite initially exposed the router-registration problem and was corrected before the final successful test execution.

---

# 59. 4 — Supplier Performance Scorecard

## 59.1 Objective

The fourth implementation stage extends the supplier statistics functionality into a supplier performance scorecard.

The scorecard combines operational Purchase Order performance and invoice performance into a single supplier-level view.

### Endpoint

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The scorecard provides:

```text
On-time delivery percentage
Dispute rate percentage
Invoice accuracy percentage
Overall supplier score
```

It also provides detailed Purchase Order and invoice counts.

---

# 60. Scorecard On-Time Delivery

The scorecard uses the same approved business rule as supplier statistics:

```text
on-time delivery percentage =
on-time Purchase Orders / total supplier Purchase Orders × 100
```

An on-time delivery is:

```text
actual_delivery_date <= expected_delivery
```

Example:

```text
Total POs = 4
On-time POs = 3

On-time delivery = 75%
```

This metric contributes:

```text
40%
```

to the overall supplier score.

---

# 61. Scorecard Dispute Rate

The dispute rate measures the percentage of supplier invoices that entered the dispute process.

Formula:

```text
dispute rate =
disputed invoices / total invoices × 100
```

An invoice is considered historically disputed when:

```python
invoice.get("dispute") is not None
```

This means the metric is based on dispute history rather than only the invoice's current status.

---

# 62. Historical Dispute Classification

An important business rule is that an invoice remains historically classified as disputed once it has entered the dispute process.

For example:

```text
Invoice Created
      ↓
Disputed
      ↓
Resolved
      ↓
Approved
```

Even after resolution, the invoice is still counted as historically disputed for supplier performance measurement.

Therefore:

```python
invoice.get("dispute") is not None
```

is treated as the source of truth for the dispute metric.

---

# 63. Invoice Accuracy

Invoice accuracy measures invoices that did not enter the dispute process.

Formula:

```text
invoice accuracy =
accurate invoices / total invoices × 100
```

The implementation defines:

```text
dispute is None → Accurate
dispute is not None → Inaccurate
```

Therefore:

```text
accurate_invoice_count
```

and:

```text
inaccurate_invoice_count
```

are derived from the supplier's invoice records.

Invoice accuracy contributes:

```text
40%
```

to the overall supplier score.

---

# 64. Dispute Performance

Because a high dispute rate represents poorer supplier performance, the scorecard converts dispute rate into a positive performance value.

Formula:

```text
dispute performance =
100 - dispute rate
```

Example:

```text
Dispute rate = 20%

Dispute performance = 100 - 20
                     = 80%
```

Dispute performance contributes:

```text
20%
```

to the overall supplier score.

---

# 65. Overall Supplier Score

The overall score combines three performance dimensions.

| Metric              | Weight |
| ------------------- | -----: |
| On-time delivery    |    40% |
| Invoice accuracy    |    40% |
| Dispute performance |    20% |

Formula:

```text
overall score =
(on-time delivery × 0.40)
+
(invoice accuracy × 0.40)
+
(dispute performance × 0.20)
```

### Example

If:

```text
On-time delivery = 75%
Invoice accuracy = 80%
Dispute performance = 90%
```

then:

```text
overall score =
(75 × 0.40)
+
(80 × 0.40)
+
(90 × 0.20)

= 30 + 32 + 18

= 80%
```

The resulting score is represented within the logical:

```text
0–100
```

performance range.

---

# 66. Scorecard Purchase Order Details

The scorecard provides detailed Purchase Order information:

```text
total
fulfilled
on_time
late
```

Example:

```json
{
    "purchase_orders": {
        "total": 4,
        "fulfilled": 3,
        "on_time": 2,
        "late": 1
    }
}
```

This allows consumers of the API to understand the underlying values behind the headline on-time percentage.

---

# 67. Scorecard Invoice Details

The scorecard provides:

```text
total
disputed
accurate
inaccurate
```

Example:

```json
{
    "invoices": {
        "total": 5,
        "disputed": 1,
        "accurate": 4,
        "inaccurate": 1
    }
}
```

These details support the calculation of:

```text
Dispute Rate
Invoice Accuracy
```

---

# 68. Supplier Existence Through Invoice Data

The scorecard supports a supplier that exists through invoice records even when that supplier currently has no Purchase Orders.

Supplier existence is therefore checked against:

```text
supplier Purchase Orders
OR
supplier invoices
```

For example:

```text
PO store:
SUP001 → no PO

Invoice store:
SUP001 → INV1001
```

The supplier is still recognized as an existing supplier.

This allows the scorecard to return invoice-based performance information instead of incorrectly returning:

```text
404 Supplier not found
```

---

# 69. Scorecard Supplier Not Found

If the supplier does not exist in either:

```text
Purchase Orders
```

or:

```text
Invoices
```

the service raises:

```text
Supplier 'SUP999' not found.
```

The route converts this into:

```http
404 Not Found
```

Example:

```json
{
    "detail": "Supplier 'SUP999' not found."
}
```

---

# 70. Scorecard Response

A successful scorecard response follows the Pydantic response schema.

Example:

```json
{
    "supplier_id": "SUP001",
    "scorecard": {
        "on_time_delivery_percentage": 50.0,
        "dispute_rate_percentage": 0.0,
        "invoice_accuracy_percentage": 100.0,
        "overall_score": 70.0
    },
    "details": {
        "purchase_orders": {
            "total": 2,
            "fulfilled": 1,
            "on_time": 1,
            "late": 0
        },
        "invoices": {
            "total": 1,
            "disputed": 0,
            "accurate": 1,
            "inaccurate": 0
        }
    }
}
```

---

# 71. Scorecard Schema Validation

The response schema validates the scorecard metrics.

The following percentage fields must remain between:

```text
0 and 100
```

including:

```text
on_time_delivery_percentage
dispute_rate_percentage
invoice_accuracy_percentage
overall_score
```

Invalid values such as:

```text
-1
101
```

are rejected by Pydantic validation.

The detail counts are also required to be non-negative.

---

# 72. 4 — Blockers Encountered

## Blocker 1 — Existing statistics were not sufficient for the scorecard

The statistics endpoint only provided:

```text
PO count
On-time delivery percentage
Average invoice cycle time
```

The scorecard required additional supplier-performance metrics.

### Resolution

A dedicated service function was introduced:

```python
calculate_supplier_scorecard()
```

This keeps the scorecard calculation separate from the general statistics calculation.

---

## Blocker 2 — Historical dispute versus current invoice state

The supplier scorecard needed to identify invoices that had entered the dispute process historically.

Simply checking:

```text
current status == disputed
```

would lose the historical information after resolution.

### Resolution

The implementation checks:

```python
invoice.get("dispute") is not None
```

An invoice that entered dispute remains classified as disputed for supplier performance measurement even after resolution.

---

## Blocker 3 — Supplier can exist through invoice data

A supplier may have:

```text
No Purchase Orders
```

but still have:

```text
Invoices
```

### Resolution

Supplier existence is evaluated using both stores:

```text
Purchase Orders
OR
Invoices
```

This allows invoice-only suppliers to receive a scorecard.

---

## Blocker 4 — Scorecard route initially returned 404

The scorecard service existed, but the API endpoint initially returned:

```text
404 Not Found
```

### Resolution

The scorecard endpoint was placed inside the supplier statistics router and the router was correctly registered with the FastAPI application.

---

## Blocker 5 — Circular router import during implementation

While registering the supplier statistics router, the application produced:

```text
AttributeError:
partially initialized module
'app.routes.supplier_stats_routes'
has no attribute 'router'
```

### Resolution

The route module was changed to define:

```python
router = APIRouter()
```

and only `main.py` performs application-level registration.

This removed the self-reference and allowed the test suite to be collected successfully.

---

## Blocker 6 — Inconsistent calculation variables

During scorecard implementation, variables from the general supplier statistics calculation could be confused with scorecard-specific variables.

Examples included:

```text
total_po_count
on_time_count
```

versus:

```text
supplier_pos
fulfilled_pos
on_time_po_count
late_po_count
```

### Resolution

The scorecard calculation was kept independent using clearly defined variables:

```text
supplier_pos
fulfilled_pos
on_time_po_count
late_po_count
total_invoice_count
disputed_invoice_count
accurate_invoice_count
inaccurate_invoice_count
```

This makes the scorecard calculation easier to maintain and test.

---

## Blocker 7 — Scorecard percentage boundaries

The scorecard response contains percentage-based metrics.

Incorrect values outside:

```text
0–100
```

must not be accepted.

### Resolution

Pydantic `Field` constraints were added:

```python
ge=0
le=100
```

for the scorecard percentage fields.

This ensures invalid scorecard responses cannot pass schema validation.

---

# 73. 3 & 4 — API Endpoints

## Supplier Statistics

| Method | Endpoint                                | Purpose                                  |
| ------ | --------------------------------------- | ---------------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/stats` | Retrieve supplier operational statistics |

## Supplier Performance Scorecard

| Method | Endpoint                                    | Purpose                                 |
| ------ | ------------------------------------------- | --------------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/scorecard` | Retrieve supplier performance scorecard |

---

# 74. 3 & 4 — Testing Strategy

Testing was implemented at multiple levels to verify both supplier statistics and scorecard behaviour.

### Supplier Statistics

Tests cover:

* Successful supplier statistics retrieval
* Supplier not found
* Purchase Order count
* All Purchase Orders on time
* No Purchase Orders on time
* Mixed on-time and late deliveries
* Unfulfilled Purchase Orders included in total
* Delivery exactly on expected date
* Missing delivery date
* Average invoice cycle time
* Date normalization
* Invalid date handling
* Negative cycle time handling
* Response schema validation
* Percentage boundaries

### Supplier Scorecard

Tests cover:

* Successful scorecard retrieval
* On-time delivery percentage
* Dispute rate
* Invoice accuracy
* Dispute performance
* Overall supplier score
* Purchase Order details
* Invoice details
* Historically disputed invoice
* Supplier not found
* Supplier existing through invoice
* Scorecard schema validation
* Percentage boundary validation

---

# 75. 3 & 4 — Test Execution

Run the complete project test suite:

```powershell
python -m pytest -v
```

Run supplier statistics and scorecard tests independently:

```powershell
python -m pytest tests/test_supplier_stats.py -v
```

The supplier statistics and scorecard implementation was tested after resolving the API router registration and circular-import issues.

The confirmed project test suite reached:

```text
39 passed
```

The remaining warning is a Starlette/HTTPX TestClient deprecation warning and does not represent a test failure.

---

# 76. 3 & 4 — Implementation Flow

```text
                 Supplier
                     │
                     ▼
          Supplier Statistics API
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       PO Count   On-Time %   Invoice Cycle
          │          │          │
          └──────────┼──────────┘
                     ▼
            Supplier Scorecard
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   On-Time %     Invoice      Dispute
                Accuracy       Rate
        │            │            │
        └────────────┼────────────┘
                     ▼
              Overall Score
```

---

# 77. 3 & 4 — Final Implementation Status

```text
┌──────────────────────────────────────────────┐
│       SUPPLIER PERFORMANCE MODULE             │
├──────────────────────────────────────────────┤
│                                              │
│  3 — Supplier Statistics                     │
│                                              │
│  PO Count                         ✓ DONE     │
│  On-Time Delivery %               ✓ DONE     │
│  Invoice Cycle Time               ✓ DONE     │
│  Date Normalization               ✓ DONE     │
│  Missing Data Handling            ✓ DONE     │
│  Supplier 404 Handling            ✓ DONE     │
│                                              │
│  4 — Supplier Scorecard                       │
│                                              │
│  On-Time Delivery %               ✓ DONE     │
│  Dispute Rate %                   ✓ DONE     │
│  Invoice Accuracy %               ✓ DONE     │
│  Dispute Performance              ✓ DONE     │
│  Overall Supplier Score            ✓ DONE     │
│  PO Details                       ✓ DONE     │
│  Invoice Details                  ✓ DONE     │
│  Invoice-Only Supplier            ✓ DONE     │
│  Schema Validation                ✓ DONE     │
│                                              │
│  API Routes                       ✓ DONE     │
│  Service Layer                    ✓ DONE     │
│  Pydantic Schemas                 ✓ DONE     │
│  Automated Tests                  ✓ DONE     │
│                                              │
└──────────────────────────────────────────────┘
```

The implementation now provides a complete supplier-performance layer combining operational delivery performance with invoice quality and dispute behaviour.

The two endpoints provide both **raw operational statistics** and a **weighted supplier performance scorecard**, while the test suite verifies the business rules, validation boundaries, error handling, and route registration.


---

# 39. API Endpoints

## Purchase Order APIs

| Method | Endpoint                                          | Purpose             |
| ------ | ------------------------------------------------- | ------------------- |
| POST   | `/api/v1/purchase-orders`                         | Create PO           |
| GET    | `/api/v1/purchase-orders`                         | Retrieve all POs    |
| GET    | `/api/v1/purchase-orders/{po_number}`             | Retrieve PO         |
| PUT    | `/api/v1/purchase-orders/{po_number}`             | Update PO           |
| DELETE | `/api/v1/purchase-orders/{po_number}`             | Delete PO           |
| POST   | `/api/v1/purchase-orders/{po_number}/acknowledge` | Acknowledge PO      |
| POST   | `/api/v1/purchase-orders/{po_number}/transition`  | Change PO state     |
| GET    | `/api/v1/purchase-orders/{po_number}/events`      | Retrieve PO history |

---

## Invoice APIs

| Method | Endpoint                                     | Purpose              |
| ------ | -------------------------------------------- | -------------------- |
| GET    | `/api/v1/invoices`                           | Retrieve invoices    |
| POST   | `/api/v1/invoices`                           | Create invoice       |
| POST   | `/api/v1/invoices/{invoice_number}/document` | Upload invoice PDF   |
| GET    | `/api/v1/invoices/{invoice_number}/document` | Download invoice PDF |

---

## Supplier APIs

| Method | Endpoint                                    | Purpose                         |
| ------ | ------------------------------------------- | ------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/stats`     | Supplier operational statistics |
| GET    | `/api/v1/suppliers/{supplier_id}/scorecard` | Supplier performance scorecard  |

---

# 40. HTTP Response Codes

| Status | Meaning                                |
| ------ | -------------------------------------- |
| 200    | Successful request                     |
| 201    | Resource created                       |
| 400    | Business-rule validation failure       |
| 404    | Resource/supplier/PO/invoice not found |
| 409    | Duplicate resource                     |
| 422    | Pydantic/request validation failure    |

---

# 41. Project Structure

```text
supplier-portal/
│
├── app/
│   ├── main.py
│   │
│   ├── routes/
│   │   ├── purchase_order.py
│   │   ├── invoice.py
│   │   └── supplier_stats_routes.py
│   │
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   ├── invoice.py
│   │   └── supplier_stats.py
│   │
│   └── services/
│       ├── purchase_order_service.py
│       ├── invoice_service.py
│       └── supplier_stats_service.py
│
├── tests/
│   ├── test_purchase_order.py
│   ├── test_invoices.py
│   └── test_supplier_stats.py
│
├── uploads/
│
├── requirements.txt
├── pytest.ini
└── README.md
```

---

# 42. Architecture

The service follows a simple layered FastAPI structure:

```text
                  HTTP Request
                       │
                       ▼
                  FastAPI Route
                       │
                       ▼
                Pydantic Schema
                       │
                       ▼
                 Service Layer
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       PO Store    Invoice Store   Event Store
          │            │            │
          └────────────┼────────────┘
                       ▼
                  HTTP Response
```

### Routes

Responsible for:

* HTTP endpoints
* Request handling
* HTTP status codes
* Calling service functions

### Schemas

Responsible for:

* Request validation
* Response validation
* Field constraints
* Percentage boundaries

### Services

Responsible for:

* Business rules
* State transitions
* Invoice validation
* Supplier calculations
* Scorecard calculations

---

# 43. Current Storage

The current implementation intentionally uses in-memory Python dictionaries.

Purchase Orders:

```python
purchase_orders = {}
```

Invoices:

```python
invoices = {}
```

Purchase Order events:

```python
po_events = {}
```

Invoice documents are stored locally under:

```text
uploads/
```

Because the service uses in-memory storage:

```text
Application restart
       │
       ▼
In-memory data cleared
```

A persistent database is planned for a future implementation.

---

# 44. Testing Strategy

Testing was implemented alongside each  rather than only at the end.

## 1 Tests

Tests cover:

* PO creation
* PO retrieval
* Get all POs
* PO update
* PO deletion
* Duplicate PO
* Acknowledgement
* Legal transitions
* Illegal transitions
* Terminal states
* Transition history
* Actor tracking
* Timestamp tracking
* PO events
* Expected delivery
* Actual delivery

---

## 2 Tests

Tests cover:

* Invoice creation
* Duplicate invoice
* Invoice number validation
* Supplier ID validation
* PO existence
* PO status
* Invoice amount validation
* Lower tolerance boundary
* Upper tolerance boundary
* Below tolerance
* Above tolerance
* PDF content type
* PDF signature
* Maximum file size
* Document upload
* Document download
* Missing document
* Path traversal protection

---

##  3 Tests

Tests cover:

* Supplier statistics
* Supplier not found
* PO count
* All POs on time
* No POs on time
* Mixed delivery performance
* Unfulfilled POs included in total
* Delivery exactly on expected date
* Missing delivery date
* Average invoice cycle time
* Date normalization
* Schema validation

---

##  Tests cases

Tests cover:

* Scorecard endpoint
* On-time delivery percentage
* Dispute rate
* Invoice accuracy
* Overall supplier score
* Scorecard PO details
* Scorecard invoice details
* Disputed invoice handling
* Supplier not found
* Supplier existing through invoice
* Scorecard schema validation
* Percentage boundary validation

---

# 45. Test Execution

Run all tests:

```powershell
python -m pytest -v
```

Run Purchase Order tests:

```powershell
python -m pytest tests/test_purchase_order.py -v
```

Run Invoice tests:

```powershell
python -m pytest tests/test_invoices.py -v
```

Run Supplier Statistics and Scorecard tests:

```powershell
python -m pytest tests/test_supplier_stats.py -v
```

The supplier statistics/scorecard test suite was expanded to cover the service, route, and schema behaviour, including the previously failing route-registration scenarios.

The latest confirmed full project test run reached:

```text
39 passed
```

The Supplier Statistics/Scorecard suite was also confirmed passing after correcting the router registration and calculation issues.

---

# 46. Known Test Warning

The test suite currently reports a Starlette/HTTPX deprecation warning related to:

```text
starlette.testclient
```

The warning does not cause test failures.

The application and test suite remain functionally passing.

---

# 47. Installation

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

---

# 48. Run the Application

From the `supplier-portal` directory:

```powershell
python -m uvicorn app.main:app --reload
```

Application:

```text
http://127.0.0.1:8000
```

---

# 49. Swagger Documentation

FastAPI automatically provides interactive API documentation.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Swagger can be used to test:

* Purchase Order CRUD
* Purchase Order acknowledgement
* Purchase Order transitions
* Purchase Order event history
* Invoice creation
* Invoice validation
* Invoice PDF upload
* Invoice PDF download
* Supplier statistics
* Supplier scorecard

---

# 50. Security Controls

## Purchase Orders

* Duplicate PO protection
* Legal state-machine enforcement
* Illegal transition rejection
* Actor tracking
* Transition timestamp tracking
* Audit event preservation

## Invoices

* Invoice number validation
* Supplier ID validation
* Duplicate invoice protection
* PO existence validation
* PO status validation
* Amount tolerance validation
* PDF content-type validation
* PDF signature validation
* Maximum file size validation
* Safe filename handling
* Path traversal protection

---

# 51. Important Business Rules

## PO Lifecycle

```text
draft
  ↓
sent
  ↓
acknowledged
  ↓
fulfilled
```

Cancellation is allowed from:

```text
draft
sent
acknowledged
```

---

## Invoice Tolerance

```text
TOLERANCE = 0.05
```

Therefore:

```text
95% <= invoice amount <= 105%
```

Boundary values are accepted.

---

## Supplier On-Time Percentage

The implemented business rule is:

```text
on-time purchase orders
------------------------ × 100
total supplier purchase orders
```

An on-time delivery is:

```text
actual_delivery_date <= expected_delivery
```

Unfulfilled POs remain included in the total denominator.

---

## Invoice Dispute Rate

```text
disputed invoices
------------------ × 100
total invoices
```

---

## Invoice Accuracy

```text
accurate invoices
------------------ × 100
total invoices
```

---

## Overall Score

```text
40% → On-time delivery
40% → Invoice accuracy
20% → Dispute performance
```

---

# 52. End-to-End Business Flow

```text
                    ADMIN
                      │
                      ▼
             Create Purchase Order
                      │
                      ▼
                    Draft
                      │
                      ▼
                    Sent
                      │
                      ▼
              Supplier Acknowledges
                      │
                      ▼
                Acknowledged
                      │
                      ▼
                  Fulfilled
                      │
                      ▼
                Submit Invoice
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     Validate PO             Validate Amount
          │                       │
          └───────────┬───────────┘
                      ▼
                Invoice Created
                      │
                      ▼
                 Upload PDF
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     Validate Type           Validate Signature
          │                       │
          └───────────┬───────────┘
                      ▼
                Store Document
                      │
                      ▼
              Supplier Statistics
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
      PO Metrics             Invoice Metrics
          │                       │
          └───────────┬───────────┘
                      ▼
             Supplier Scorecard
```

---

# 53.  Implementation Summary

##  1 — Purchase Orders

### Implemented

```text
CRUD
Acknowledgement
State machine
Legal transitions
Illegal transition rejection
Audit history
Events endpoint
Actor tracking
Timestamp tracking
Delivery tracking
```

### Major blockers resolved

```text
State transition enforcement
Incomplete transition history
History visibility
Delivery outcome tracking
```

---

##  2 — Invoices

### Implemented

```text
Invoice creation
Validation
Duplicate protection
PO validation
PO status validation
Amount tolerance
PDF upload
PDF signature validation
PDF size validation
Secure document storage
PDF download
Path traversal protection
```

### Major blockers resolved

```text
Tolerance boundary handling
PDF type spoofing
File size validation
Secure filesystem paths
Document response handling
```

---

##  3 — Supplier Statistics

### Implemented

```text
PO count
On-time percentage
Average invoice cycle time
Date normalization
Missing-data handling
Supplier not-found handling
```

### Major blockers resolved

```text
Correct on-time denominator
Missing delivery dates
Mixed date formats
Supplier stats 404
Router registration
Circular import
```

---

##  4 — Supplier Scorecard

### Implemented

```text
On-time delivery %
Dispute rate %
Invoice accuracy %
Dispute performance
Overall score
PO details
Invoice details
Supplier existence through invoices
```

### Major blockers resolved

```text
Scorecard-specific calculations
Historical dispute classification
Supplier existence through invoice
Scorecard route 404
Inconsistent calculation variables
Schema boundary validation
```

---

# 54. Final Implementation Status

```text
┌─────────────────────────────────────────────┐
│        SUPPLIER PORTAL SERVICE              │
├─────────────────────────────────────────────┤
│                                             │
│  1                                     │
│  Purchase Order Management        ✓ DONE    │
│                                             │
│  2                                     │
│  Invoice Management               ✓ DONE    │
│                                             │
│   3                                     │
│  Supplier Statistics              ✓ DONE    │
│                                             │
│   4                                     │
│  Supplier Scorecard               ✓ DONE    │
│                                             │
│  Automated Testing                ✓ DONE    │
│                                             │
└─────────────────────────────────────────────┘
```

The current service provides a complete working backend flow from:

```text
Purchase Order
      ↓
PO Lifecycle
      ↓
PO Fulfilment
      ↓
Invoice
      ↓
Invoice Document
      ↓
Supplier Statistics
      ↓
Supplier Performance Scorecard
```

The implementation is currently suitable for the next development phase involving persistent storage, authentication, infrastructure, and production deployment.

---

# 55. Future Enhancements

The current implementation intentionally uses in-memory storage and local document storage.

Future production enhancements can include:

* PostgreSQL
* SQLAlchemy ORM
* Database migrations
* Kafka event streaming
* Redis caching
* MinIO/S3 object storage
* JWT authentication
* Role-based access control
* Docker
* Kubernetes
* API Gateway integration
* Centralized configuration
* Structured logging
* Monitoring
* Distributed tracing
* CI/CD
* Persistent audit storage

---

# 56. Current Status

**Supplier Portal Service — Completed**

```text
Purchase Orders        ✓
PO State Machine       ✓
PO Audit History       ✓
Delivery Tracking      ✓

Invoices               ✓
Invoice Validation     ✓
Amount Tolerance       ✓
PDF Upload             ✓
PDF Security           ✓
PDF Download           ✓

Supplier Statistics    ✓
PO Count               ✓
On-Time Delivery %     ✓
Invoice Cycle Time     ✓

Supplier Scorecard     ✓
Dispute Rate           ✓
Invoice Accuracy       ✓
Overall Score          ✓

Automated Tests        ✓
API Routes             ✓
Pydantic Schemas       ✓
Swagger Documentation  ✓
```

The service is ready for the next stage of the Enterprise AI Cognitive Supply Chain Platform.
