from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# SUPPLIER ONBOARDING STATUS
# ============================================================

class SupplierOnboardingStatus(str, Enum):
    pending_documents = "pending_documents"
    documents_submitted = "documents_submitted"
    verified = "verified"
    approved = "approved"
    active = "active"


# ============================================================
# DOCUMENT STATUS
# ============================================================

class SupplierDocumentStatus(str, Enum):
    submitted = "submitted"
    verified = "verified"
    rejected = "rejected"


# ============================================================
# DOCUMENT RESPONSE
# ============================================================

class SupplierDocumentResponse(BaseModel):
    document_id: str
    supplier_id: str
    document_type: str
    file_name: str
    document_path: str
    status: SupplierDocumentStatus
    uploaded_at: datetime
    uploaded_by: str


# ============================================================
# SUPPLIER REGISTRATION
# ============================================================

class SupplierRegistration(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_id": "SUP001",
                "company_name": "ABC Supplies Pvt Ltd",
                "contact_name": "Ravi Kumar",
                "email": "ravi@abcsupplies.com",
                "phone": "9876543210",
                "address": "Hyderabad, Telangana",
                "required_documents": [
                    "gst_certificate",
                    "pan_card",
                    "bank_certificate"
                ]
            }
        }
    )

    supplier_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    company_name: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    contact_name: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    email: str = Field(
        ...,
        min_length=5,
        max_length=255
    )

    phone: str = Field(
        ...,
        min_length=5,
        max_length=30
    )

    address: str = Field(
        ...,
        min_length=5,
        max_length=500
    )

    required_documents: list[str] = Field(
        ...,
        min_length=1
    )


# ============================================================
# SUPPLIER RESPONSE
# ============================================================

class SupplierOnboardingResponse(BaseModel):
    supplier_id: str
    company_name: str
    contact_name: str
    email: str
    phone: str
    address: str
    status: SupplierOnboardingStatus
    required_documents: list[str]
    created_at: datetime
    updated_at: datetime


# ============================================================
# VERIFICATION RESPONSE
# ============================================================

class SupplierVerificationResponse(BaseModel):
    supplier_id: str
    status: SupplierOnboardingStatus
    verification_result: str
    verified_at: datetime
    verified_by: str


# ============================================================
# APPROVAL REQUEST
# ============================================================

class SupplierApprovalRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Supplier documents and verification completed successfully"
            }
        }
    )

    reason: str | None = Field(
        default=None,
        max_length=1000
    )


# ============================================================
# APPROVAL RESPONSE
# ============================================================

class SupplierApprovalResponse(BaseModel):
    supplier_id: str
    status: SupplierOnboardingStatus
    approved_at: datetime
    approved_by: str
    reason: str | None = None


# ============================================================
# ACTIVATION RESPONSE
# ============================================================

class SupplierActivationResponse(BaseModel):
    supplier_id: str
    status: SupplierOnboardingStatus
    activated_at: datetime
    activated_by: str


# ============================================================
# STATUS RESPONSE
# ============================================================

class SupplierStatusResponse(BaseModel):
    supplier_id: str
    status: SupplierOnboardingStatus
    required_documents: list[str]
    submitted_documents: list[str]
    missing_documents: list[str]


# ============================================================
# AUDIT HISTORY
# ============================================================

class SupplierOnboardingHistory(BaseModel):
    history_id: str
    supplier_id: str
    from_status: SupplierOnboardingStatus | None
    to_status: SupplierOnboardingStatus
    actor_id: str
    actor_name: str
    role: str
    reason: str | None
    timestamp: datetime

