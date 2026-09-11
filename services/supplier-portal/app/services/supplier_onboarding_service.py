from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import UploadFile

from app.schemas.supplier_onboarding import (
    SupplierApprovalRequest,
    SupplierDocumentStatus,
    SupplierOnboardingStatus,
)


# ============================================================
# STORAGE
# ============================================================

suppliers: dict[str, dict] = {}

supplier_documents: dict[str, list[dict]] = {}

supplier_onboarding_history: dict[str, list[dict]] = {}


# ============================================================
# STATE TRANSITIONS
# ============================================================

SUPPLIER_ONBOARDING_TRANSITIONS = {
    SupplierOnboardingStatus.pending_documents: [
        SupplierOnboardingStatus.documents_submitted,
    ],
    SupplierOnboardingStatus.documents_submitted: [
        SupplierOnboardingStatus.verified,
    ],
    SupplierOnboardingStatus.verified: [
        SupplierOnboardingStatus.approved,
    ],
    SupplierOnboardingStatus.approved: [
        SupplierOnboardingStatus.active,
    ],
    SupplierOnboardingStatus.active: [],
}


# ============================================================
# HELPERS
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _add_history(
    supplier_id: str,
    from_status,
    to_status,
    actor_id: str,
    actor_name: str,
    role: str,
    reason: str | None = None,
):
    history = {
        "history_id": str(uuid.uuid4()),
        "supplier_id": supplier_id,
        "from_status": from_status,
        "to_status": to_status,
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "role": role,
        "reason": reason,
        "timestamp": _utc_now(),
    }

    supplier_onboarding_history.setdefault(
        supplier_id,
        [],
    ).append(history)

    return history


def _transition(
    supplier_id: str,
    target_status: SupplierOnboardingStatus,
    actor_id: str,
    actor_name: str,
    role: str,
    reason: str | None = None,
):
    supplier = suppliers.get(supplier_id)

    if supplier is None:
        raise ValueError("Supplier not found.")

    current_status = supplier["status"]

    allowed_states = SUPPLIER_ONBOARDING_TRANSITIONS.get(
        current_status,
        [],
    )

    if target_status not in allowed_states:
        allowed = ", ".join(
            state.value for state in allowed_states
        )

        if not allowed:
            allowed = "none"

        raise ValueError(
            f"Cannot move supplier '{supplier_id}' "
            f"from status '{current_status.value}' "
            f"to '{target_status.value}'. "
            f"Allowed: {allowed}."
        )

    supplier["status"] = target_status
    supplier["updated_at"] = _utc_now()

    _add_history(
        supplier_id=supplier_id,
        from_status=current_status,
        to_status=target_status,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason=reason,
    )

    return supplier


# ============================================================
# 1. REGISTER SUPPLIER
# ============================================================

def register_supplier(
    registration,
    actor_id: str,
    actor_name: str,
    role: str,
):
    supplier_id = registration.supplier_id.strip()

    if not supplier_id:
        raise ValueError(
            "Supplier ID is required."
        )

    if supplier_id in suppliers:
        raise ValueError(
            f"Supplier '{supplier_id}' is already registered."
        )

    now = _utc_now()

    supplier = {
        "supplier_id": supplier_id,
        "company_name": registration.company_name,
        "contact_name": registration.contact_name,
        "email": registration.email,
        "phone": registration.phone,
        "address": registration.address,
        "status": SupplierOnboardingStatus.pending_documents,
        "required_documents": list(
            registration.required_documents
        ),
        "created_at": now,
        "updated_at": now,
    }

    suppliers[supplier_id] = supplier

    supplier_documents[supplier_id] = []

    supplier_onboarding_history[supplier_id] = []

    _add_history(
        supplier_id=supplier_id,
        from_status=None,
        to_status=SupplierOnboardingStatus.pending_documents,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason="Supplier registration created.",
    )

    return supplier


# ============================================================
# 2. GET SUPPLIER
# ============================================================

def get_supplier(supplier_id: str):
    supplier = suppliers.get(supplier_id)

    if supplier is None:
        raise ValueError(
            "Supplier not found."
        )

    return supplier


# ============================================================
# 3. UPLOAD DOCUMENT
# ============================================================

def upload_supplier_document(
    supplier_id: str,
    document_type: str,
    file: UploadFile,
    actor_id: str,
    actor_name: str,
):
    supplier = get_supplier(supplier_id)

    if supplier["status"] not in [
        SupplierOnboardingStatus.pending_documents,
        SupplierOnboardingStatus.documents_submitted,
    ]:
        raise ValueError(
            "Documents can only be uploaded before verification."
        )

    document_type = document_type.strip()

    if not document_type:
        raise ValueError(
            "Document type is required."
        )

    if document_type not in supplier["required_documents"]:
        raise ValueError(
            f"Document type '{document_type}' "
            "is not required for this supplier."
        )

    documents = supplier_documents.setdefault(
        supplier_id,
        [],
    )

    existing = next(
        (
            item
            for item in documents
            if item["document_type"] == document_type
            and item["status"]
            != SupplierDocumentStatus.rejected
        ),
        None,
    )

    if existing:
        raise ValueError(
            f"Document '{document_type}' "
            "has already been submitted."
        )

    original_name = file.filename or "document"

    upload_directory = (
        Path("uploads")
        / "supplier_onboarding"
        / supplier_id
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    document_id = str(uuid.uuid4())

    safe_name = (
        f"{document_id}_{Path(original_name).name}"
    )

    document_path = upload_directory / safe_name

    content = file.file.read()

    if not content:
        raise ValueError(
            "Uploaded document is empty."
        )

    document_path.write_bytes(content)

    document = {
        "document_id": document_id,
        "supplier_id": supplier_id,
        "document_type": document_type,
        "file_name": original_name,
        "document_path": str(document_path),
        "status": SupplierDocumentStatus.submitted,
        "uploaded_at": _utc_now(),
        "uploaded_by": str(actor_id),
    }

    documents.append(document)

    required_documents = set(
        supplier["required_documents"]
    )

    submitted_documents = {
        item["document_type"]
        for item in documents
        if item["status"]
        != SupplierDocumentStatus.rejected
    }

    if required_documents.issubset(
        submitted_documents
    ):
        if (
            supplier["status"]
            == SupplierOnboardingStatus.pending_documents
        ):
            _transition(
                supplier_id=supplier_id,
                target_status=(
                    SupplierOnboardingStatus.documents_submitted
                ),
                actor_id=actor_id,
                actor_name=actor_name,
                role="supplier",
                reason="All required documents submitted.",
            )

    return document


# ============================================================
# 4. LIST DOCUMENTS
# ============================================================

def list_supplier_documents(
    supplier_id: str,
):
    get_supplier(supplier_id)

    return supplier_documents.get(
        supplier_id,
        [],
    )


# ============================================================
# 5. MOCK VERIFICATION
# ============================================================

def verify_supplier(
    supplier_id: str,
    actor_id: str,
    actor_name: str,
    role: str,
):
    supplier = get_supplier(supplier_id)

    if (
        supplier["status"]
        != SupplierOnboardingStatus.documents_submitted
    ):
        raise ValueError(
            "Supplier must have all required documents "
            "submitted before verification."
        )

    required_documents = set(
        supplier["required_documents"]
    )

    documents = supplier_documents.get(
        supplier_id,
        [],
    )

    submitted_documents = {
        item["document_type"]
        for item in documents
        if item["status"]
        != SupplierDocumentStatus.rejected
    }

    missing_documents = (
        required_documents - submitted_documents
    )

    if missing_documents:
        raise ValueError(
            "Missing required documents: "
            + ", ".join(
                sorted(missing_documents)
            )
        )

    for document in documents:
        if (
            document["document_type"]
            in required_documents
        ):
            document["status"] = (
                SupplierDocumentStatus.verified
            )

    supplier = _transition(
        supplier_id=supplier_id,
        target_status=SupplierOnboardingStatus.verified,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason="Mock verification passed.",
    )

    return {
        "supplier_id": supplier_id,
        "status": supplier["status"],
        "verification_result": "passed",
        "verified_at": supplier["updated_at"],
        "verified_by": actor_id,
    }


# ============================================================
# 6. APPROVE SUPPLIER
# ============================================================

def approve_supplier(
    supplier_id: str,
    approval: SupplierApprovalRequest,
    actor_id: str,
    actor_name: str,
    role: str,
):
    supplier = _transition(
        supplier_id=supplier_id,
        target_status=SupplierOnboardingStatus.approved,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason=approval.reason,
    )

    return {
        "supplier_id": supplier_id,
        "status": supplier["status"],
        "approved_at": supplier["updated_at"],
        "approved_by": actor_id,
        "reason": approval.reason,
    }


# ============================================================
# 7. ACTIVATE SUPPLIER
# ============================================================

def activate_supplier(
    supplier_id: str,
    actor_id: str,
    actor_name: str,
    role: str,
):
    supplier = _transition(
        supplier_id=supplier_id,
        target_status=SupplierOnboardingStatus.active,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason="Supplier activated.",
    )

    return {
        "supplier_id": supplier_id,
        "status": supplier["status"],
        "activated_at": supplier["updated_at"],
        "activated_by": actor_id,
    }


# ============================================================
# 8. LIST SUPPLIERS
# ============================================================

def list_suppliers():
    return list(
        suppliers.values()
    )


# ============================================================
# 9. SUPPLIER STATUS
# ============================================================

def get_supplier_status(
    supplier_id: str,
):
    supplier = get_supplier(supplier_id)

    required_documents = set(
        supplier["required_documents"]
    )

    documents = supplier_documents.get(
        supplier_id,
        [],
    )

    submitted_documents = {
        item["document_type"]
        for item in documents
        if item["status"]
        != SupplierDocumentStatus.rejected
    }

    missing_documents = (
        required_documents - submitted_documents
    )

    return {
        "supplier_id": supplier_id,
        "status": supplier["status"],
        "required_documents": sorted(
            required_documents
        ),
        "submitted_documents": sorted(
            submitted_documents
        ),
        "missing_documents": sorted(
            missing_documents
        ),
    }


# ============================================================
# 10. ONBOARDING HISTORY
# ============================================================

def get_supplier_history(
    supplier_id: str,
):
    get_supplier(supplier_id)

    return supplier_onboarding_history.get(
        supplier_id,
        [],
    )

