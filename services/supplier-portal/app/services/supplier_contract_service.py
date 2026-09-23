from datetime import date, datetime, timezone
import uuid

from app.schemas.supplier_contract import (
    ContractStatus,
    SupplierContractCreate,
    SupplierContractRenewalRequest,
    SupplierContractUpdate,
)


# ============================================================
# STORAGE
# ============================================================

supplier_contracts: dict[str, dict] = {}

supplier_contract_history: dict[str, list[dict]] = {}


# ============================================================
# CONTRACT STATE TRANSITIONS
# ============================================================

CONTRACT_TRANSITIONS = {
    ContractStatus.draft: [
        ContractStatus.active,
    ],
    ContractStatus.active: [],
    ContractStatus.renewed: [
        ContractStatus.active,
    ],
    ContractStatus.expired: [],
}


# ============================================================
# HELPERS
# ============================================================

def _utc_now() -> datetime:
    """
    Return the current UTC timestamp.

    All persisted contract timestamps use UTC so that
    the service behaves consistently across environments.
    """
    return datetime.now(timezone.utc)


def _calculate_days_until_expiry(
    end_date: date,
) -> int:
    """
    Return the number of calendar days from today until
    the contract end date.

    Positive value:
        Contract has not expired.

    Zero:
        Contract expires today.

    Negative value:
        Contract has already expired.
    """
    return (end_date - date.today()).days


def _is_expired(
    end_date: date,
) -> bool:
    """
    A contract is expired when its end date is before today.

    A contract expiring today is still considered valid for
    the current day.
    """
    return end_date < date.today()


def _is_expiring_soon(
    end_date: date,
    renewal_notice_days: int,
) -> bool:
    """
    Return True when the contract is still valid and its
    remaining lifetime is inside the configured renewal
    notification window.
    """
    days_until_expiry = _calculate_days_until_expiry(
        end_date
    )

    return (
        days_until_expiry >= 0
        and days_until_expiry <= renewal_notice_days
    )


def _effective_status(
    contract: dict,
) -> ContractStatus:
    """
    Calculate the current effective contract status.

    Expiration is derived dynamically from end_date rather
    than requiring a background scheduler.
    """
    if _is_expired(
        contract["end_date"]
    ):
        return ContractStatus.expired

    return ContractStatus(
        contract["status"]
    )


def _add_history(
    contract_id: str,
    supplier_id: str,
    from_status: ContractStatus | None,
    to_status: ContractStatus,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    reason: str | None = None,
):
    """
    Add an immutable lifecycle/audit record.

    History is used for both:
        - lifecycle transitions
        - contract term modifications

    For term modifications, from_status and to_status
    can be the same status.
    """

    history = {
        "history_id": str(
            uuid.uuid4()
        ),
        "contract_id": contract_id,
        "supplier_id": supplier_id,
        "from_status": from_status,
        "to_status": to_status,
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "role": actor_role,
        "reason": reason,
        "timestamp": _utc_now(),
    }

    supplier_contract_history.setdefault(
        contract_id,
        [],
    ).append(history)

    return history


def _transition(
    contract_id: str,
    target_status: ContractStatus,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    reason: str | None = None,
):
    """
    Perform a controlled contract lifecycle transition.
    """

    contract = supplier_contracts.get(
        contract_id
    )

    if contract is None:
        raise ValueError(
            "Contract not found."
        )

    current_status = _effective_status(
        contract
    )

    allowed_states = CONTRACT_TRANSITIONS.get(
        current_status,
        [],
    )

    if target_status not in allowed_states:
        allowed = ", ".join(
            state.value
            for state in allowed_states
        )

        if not allowed:
            allowed = "none"

        raise ValueError(
            f"Cannot move contract "
            f"'{contract_id}' "
            f"from status "
            f"'{current_status.value}' "
            f"to status "
            f"'{target_status.value}'. "
            f"Allowed: {allowed}."
        )

    contract["status"] = target_status

    contract["updated_at"] = _utc_now()

    _add_history(
        contract_id=contract_id,
        supplier_id=contract["supplier_id"],
        from_status=current_status,
        to_status=target_status,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        reason=reason,
    )

    return contract


# ============================================================
# SUPPLIER VALIDATION
# ============================================================

def _validate_supplier_active(
    supplier_id: str,
):
    """
    Contract creation is allowed only for an active supplier.

    Import is intentionally local so the onboarding service
    and contract service do not create an unnecessary
    module-level circular dependency.
    """
    from app.services.supplier_onboarding_service import (
        get_supplier,
        is_supplier_active,
    )

    try:
        get_supplier(
            supplier_id
        )
    except ValueError:
        raise ValueError(
            "Supplier not found."
        )

    if not is_supplier_active(
        supplier_id
    ):
        raise ValueError(
            "Contract can only be created for an active supplier."
        )


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def _validate_contract_dates(
    start_date: date,
    end_date: date,
) -> None:
    """
    Validate the contract date range.

    Historical/expired contracts are allowed because they are
    useful for contract history and reporting.

    The only invalid condition is an end date before the
    start date.
    """
    if end_date < start_date:
        raise ValueError(
            "Contract end_date must be on or after start_date."
        )


def _validate_renewal_dates(
    current_contract: dict,
    new_start_date: date,
    new_end_date: date,
):
    """
    Validate a renewal period.

    The renewed contract cannot overlap the previous contract
    period.

    The new contract may start on the previous contract's
    end date or later.
    """
    current_end_date = current_contract[
        "end_date"
    ]

    if new_start_date < current_end_date:
        raise ValueError(
            "Renewal start date cannot be before "
            "the current contract end date."
        )

    if new_end_date <= new_start_date:
        raise ValueError(
            "Renewal end date must be after renewal start date."
        )


def _find_contract_by_number(
    contract_number: str,
):
    """
    Find an existing contract by contract number.

    Contract numbers are treated case-insensitively.
    """
    normalized_number = (
        contract_number.strip().lower()
    )

    for contract in supplier_contracts.values():
        existing_number = (
            contract["contract_number"]
            .strip()
            .lower()
        )

        if existing_number == normalized_number:
            return contract

    return None


# ============================================================
# RESPONSE BUILDING
# ============================================================

def _build_contract_response(
    contract: dict,
) -> dict:
    """
    Build the public contract representation.

    Expiry-related fields are always calculated dynamically.
    """
    days_until_expiry = _calculate_days_until_expiry(
        contract["end_date"]
    )

    effective_status = _effective_status(
        contract
    )

    expiring_soon = (
        effective_status != ContractStatus.expired
        and _is_expiring_soon(
            contract["end_date"],
            contract["renewal_notice_days"],
        )
    )

    return {
        "contract_id": contract["contract_id"],
        "supplier_id": contract["supplier_id"],
        "contract_number": contract["contract_number"],
        "title": contract["title"],
        "description": contract["description"],
        "start_date": contract["start_date"],
        "end_date": contract["end_date"],
        "payment_terms": contract["payment_terms"],
        "delivery_terms": contract["delivery_terms"],
        "pricing_terms": contract["pricing_terms"],
        "minimum_order_value": (
            contract["minimum_order_value"]
        ),
        "renewal_notice_days": (
            contract["renewal_notice_days"]
        ),
        "auto_renew": contract["auto_renew"],
        "status": effective_status,
        "expiring_soon": expiring_soon,
        "days_until_expiry": days_until_expiry,
        "created_at": contract["created_at"],
        "updated_at": contract["updated_at"],
        "created_by": contract["created_by"],
    }


# ============================================================
# 1. CREATE CONTRACT
# ============================================================

def create_contract(
    contract_data: SupplierContractCreate,
    actor_id: str,
    actor_name: str,
    role: str,
):
    """
    Create a new supplier contract in DRAFT state.

    Business rules:
        1. Supplier must exist.
        2. Supplier must be ACTIVE.
        3. Contract number must be unique.
        4. End date must be on or after start date.
        5. Historical/expired contracts are allowed.
    """

    supplier_id = (
        contract_data.supplier_id.strip()
    )

    contract_number = (
        contract_data.contract_number.strip()
    )

    if not supplier_id:
        raise ValueError(
            "Supplier ID is required."
        )

    if not contract_number:
        raise ValueError(
            "Contract number is required."
        )

    _validate_supplier_active(
        supplier_id
    )

    _validate_contract_dates(
        contract_data.start_date,
        contract_data.end_date,
    )

    existing = _find_contract_by_number(
        contract_number
    )

    if existing:
        raise ValueError(
            f"Contract number '{contract_number}' "
            "already exists."
        )

    now = _utc_now()

    contract_id = (
        f"CNT-{uuid.uuid4().hex[:8].upper()}"
    )

    contract = {
        "contract_id": contract_id,
        "supplier_id": supplier_id,
        "contract_number": contract_number,
        "title": contract_data.title,
        "description": contract_data.description,
        "start_date": contract_data.start_date,
        "end_date": contract_data.end_date,
        "payment_terms": contract_data.payment_terms,
        "delivery_terms": contract_data.delivery_terms,
        "pricing_terms": contract_data.pricing_terms,
        "minimum_order_value": (
            contract_data.minimum_order_value
        ),
        "renewal_notice_days": (
            contract_data.renewal_notice_days
        ),
        "auto_renew": contract_data.auto_renew,
        "status": ContractStatus.draft,
        "created_at": now,
        "updated_at": now,
        "created_by": str(actor_id),
    }

    supplier_contracts[
        contract_id
    ] = contract

    supplier_contract_history[
        contract_id
    ] = []

    _add_history(
        contract_id=contract_id,
        supplier_id=supplier_id,
        from_status=None,
        to_status=ContractStatus.draft,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=role,
        reason="Supplier contract created.",
    )

    return _build_contract_response(
        contract
    )


# ============================================================
# 2. GET CONTRACT
# ============================================================

def get_contract(
    contract_id: str,
):
    """
    Return a contract by ID with its current
    effective lifecycle status.
    """

    contract = supplier_contracts.get(
        contract_id
    )

    if contract is None:
        raise ValueError(
            "Contract not found."
        )

    return _build_contract_response(
        contract
    )


# ============================================================
# 3. LIST CONTRACTS
# ============================================================

def list_contracts(
    supplier_id: str | None = None,
    status: ContractStatus | None = None,
):
    """
    List contracts with optional supplier/status filters.

    Expired status is calculated dynamically.
    """

    results = []

    for contract in supplier_contracts.values():

        effective_status = _effective_status(
            contract
        )

        if (
            supplier_id is not None
            and contract["supplier_id"] != supplier_id
        ):
            continue

        if (
            status is not None
            and effective_status != status
        ):
            continue

        results.append(
            _build_contract_response(
                contract
            )
        )

    results.sort(
        key=lambda item: (
            item["end_date"],
            item["contract_id"],
        )
    )

    return results


# ============================================================
# 4. UPDATE CONTRACT
# ============================================================

def update_contract(
    contract_id: str,
    contract_data: SupplierContractUpdate,
    actor_id: str | None = None,
    actor_name: str | None = None,
    actor_role: str | None = None,
):
    """
    Update editable contract terms.

    Lifecycle changes such as activation and renewal use
    dedicated operations.

    Expired contracts cannot be modified.

    Every actual contract-term change is recorded in the
    contract history for audit purposes.
    """

    contract = supplier_contracts.get(
        contract_id
    )

    if contract is None:
        raise ValueError(
            "Contract not found."
        )

    effective_status = _effective_status(
        contract
    )

    if effective_status == ContractStatus.expired:
        raise ValueError(
            "Expired contracts cannot be updated."
        )

    update_data = contract_data.model_dump(
        exclude_unset=True
    )

    if not update_data:
        raise ValueError(
            "At least one contract field must be provided."
        )

    new_start_date = contract[
        "start_date"
    ]

    new_end_date = update_data.get(
        "end_date",
        contract["end_date"],
    )

    _validate_contract_dates(
        new_start_date,
        new_end_date,
    )

    # --------------------------------------------------------
    # Capture actual field-level changes BEFORE updating
    # --------------------------------------------------------

    changes = {}

    for field, new_value in update_data.items():

        old_value = contract.get(
            field
        )

        if old_value != new_value:
            changes[field] = {
                "old_value": old_value,
                "new_value": new_value,
            }

    # --------------------------------------------------------
    # Apply changes
    # --------------------------------------------------------

    for field, value in update_data.items():
        contract[field] = value

    contract["updated_at"] = _utc_now()

    # --------------------------------------------------------
    # Audit history
    # --------------------------------------------------------

    if changes:

        changed_fields = ", ".join(
            changes.keys()
        )

        history_reason = (
            "Contract terms updated. "
            f"Changed fields: {changed_fields}. "
            f"Changes: {changes}"
        )

        # IMPORTANT:
        # _add_history() requires contract_id and supplier_id.
        # Do not pass the contract dictionary as the first
        # positional argument.
        _add_history(
            contract_id=contract_id,
            supplier_id=contract["supplier_id"],
            from_status=effective_status,
            to_status=effective_status,
            actor_id=(
                str(actor_id)
                if actor_id is not None
                else "system"
            ),
            actor_name=(
                actor_name
                if actor_name
                else "System"
            ),
            actor_role=(
                actor_role
                if actor_role
                else "system"
            ),
            reason=history_reason,
        )

    return _build_contract_response(
        contract
    )


# ============================================================
# 5. ACTIVATE CONTRACT
# ============================================================

def activate_contract(
    contract_id: str,
    actor_id: str,
    actor_name: str,
    role: str,
):
    """
    Move a contract from DRAFT to ACTIVE.

    An already expired contract cannot be activated.
    """

    contract = supplier_contracts.get(
        contract_id
    )

    if contract is None:
        raise ValueError(
            "Contract not found."
        )

    if _is_expired(
        contract["end_date"]
    ):
        raise ValueError(
            "An already expired contract cannot be activated."
        )

    return _build_contract_response(
        _transition(
            contract_id=contract_id,
            target_status=ContractStatus.active,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=role,
            reason="Supplier contract activated.",
        )
    )


# ============================================================
# 6. RENEW CONTRACT
# ============================================================

def renew_contract(
    contract_id: str,
    renewal_data: SupplierContractRenewalRequest,
    actor_id: str,
    actor_name: str,
    role: str,
):
    """
    Renew an active or expired contract.

    The old validity period is preserved in the lifecycle
    history through the renewal reason.

    The contract receives the new validity period and becomes
    ACTIVE again.
    """

    contract = supplier_contracts.get(
        contract_id
    )

    if contract is None:
        raise ValueError(
            "Contract not found."
        )

    effective_status = _effective_status(
        contract
    )

    if effective_status not in (
        ContractStatus.active,
        ContractStatus.expired,
    ):
        raise ValueError(
            "Only active or expired contracts "
            "can be renewed."
        )

    _validate_renewal_dates(
        current_contract=contract,
        new_start_date=renewal_data.new_start_date,
        new_end_date=renewal_data.new_end_date,
    )

    previous_start_date = contract[
        "start_date"
    ]

    previous_end_date = contract[
        "end_date"
    ]

    previous_status = effective_status

    renewal_reason = (
        renewal_data.reason
        or "Supplier contract renewed."
    )

    # Preserve the previous validity period in the
    # immutable history reason.
    history_reason = (
        f"{renewal_reason} "
        f"Previous period: "
        f"{previous_start_date.isoformat()} "
        f"to {previous_end_date.isoformat()}. "
        f"New period: "
        f"{renewal_data.new_start_date.isoformat()} "
        f"to {renewal_data.new_end_date.isoformat()}."
    )

    contract["start_date"] = (
        renewal_data.new_start_date
    )

    contract["end_date"] = (
        renewal_data.new_end_date
    )

    contract["status"] = ContractStatus.active

    contract["updated_at"] = _utc_now()

    _add_history(
        contract_id=contract_id,
        supplier_id=contract["supplier_id"],
        from_status=previous_status,
        to_status=ContractStatus.active,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=role,
        reason=history_reason,
    )

    return {
        "contract_id": contract_id,
        "supplier_id": contract["supplier_id"],
        "status": ContractStatus.active,
        "previous_end_date": previous_end_date,
        "new_start_date": renewal_data.new_start_date,
        "new_end_date": renewal_data.new_end_date,
        "renewed_at": contract["updated_at"],
        "renewed_by": str(actor_id),
        "reason": renewal_data.reason,
    }


# ============================================================
# 7. LIST EXPIRING CONTRACTS
# ============================================================

def list_expiring_contracts(
    supplier_id: str | None = None,
    within_days: int | None = None,
):
    """
    Return non-expired contracts that are inside their
    renewal notification window.

    A contract can be DRAFT or ACTIVE and still generate a
    renewal alert.

    The contract's own renewal_notice_days defines its
    default notification window.

    If within_days is provided, it acts as an additional
    upper bound.
    """

    if within_days is not None and within_days < 0:
        raise ValueError(
            "within_days cannot be negative."
        )

    results = []

    for contract in supplier_contracts.values():

        effective_status = _effective_status(
            contract
        )

        # Expired contracts never appear in the renewal
        # alert list.
        if effective_status == ContractStatus.expired:
            continue

        if (
            supplier_id is not None
            and contract["supplier_id"] != supplier_id
        ):
            continue

        days_until_expiry = (
            _calculate_days_until_expiry(
                contract["end_date"]
            )
        )

        renewal_window = (
            contract["renewal_notice_days"]
        )

        if within_days is not None:
            renewal_window = min(
                renewal_window,
                within_days,
            )

        if (
            0
            <= days_until_expiry
            <= renewal_window
        ):
            results.append(
                {
                    "contract_id": contract["contract_id"],
                    "supplier_id": contract["supplier_id"],
                    "contract_number": (
                        contract["contract_number"]
                    ),
                    "title": contract["title"],
                    "end_date": contract["end_date"],
                    "renewal_notice_days": (
                        contract["renewal_notice_days"]
                    ),
                    "days_until_expiry": (
                        days_until_expiry
                    ),
                    "expiring_soon": True,
                    "status": effective_status,
                }
            )

    results.sort(
        key=lambda item: (
            item["days_until_expiry"],
            item["contract_id"],
        )
    )

    return results


# ============================================================
# 8. CONTRACT HISTORY
# ============================================================

def get_contract_history(
    contract_id: str,
):
    """
    Return immutable lifecycle and audit history for a
    contract.
    """

    if contract_id not in supplier_contracts:
        raise ValueError(
            "Contract not found."
        )

    return supplier_contract_history.get(
        contract_id,
        [],
    )