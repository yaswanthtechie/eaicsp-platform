from datetime import datetime
from enum import Enum
from typing import Optional

import strawberry
from sqlalchemy import case, func

from app.core.config import INTERNAL_BLOCK_MATCH_SCORE
from app.core.database import SessionLocal
from app.models.audit import ComplianceAudit
from app.models.compliance_case import ComplianceCase
from app.services.audit_service import compute_decision


# ============================================================
# GRAPHQL ENUMS
# ============================================================


@strawberry.enum
class ScreeningStatus(Enum):
    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


@strawberry.enum
class CaseStatus(Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLEARED = "CLEARED"
    CONFIRMED = "CONFIRMED"


# ============================================================
# GRAPHQL TYPES
# ============================================================


@strawberry.type
class Screening:
    id: int
    entity_name: str
    country: Optional[str]
    status: ScreeningStatus
    matched: bool
    matched_name: Optional[str]
    matched_lists: Optional[str]
    match_score: int
    risk_score: float
    screening_type: str
    newly_flagged: bool
    screening_run_id: Optional[str]
    duration_ms: float
    created_at: datetime


@strawberry.type
class Case:
    id: int
    case_number: str
    entity_name: str
    entity_type: str
    country: Optional[str]
    matched_name: Optional[str]
    matched_lists: Optional[str]
    match_score: int
    risk_score: float
    screening_tier: Optional[str]
    screening_action: Optional[str]
    status: CaseStatus
    assigned_to: Optional[str]
    assigned_at: Optional[datetime]
    resolution: Optional[str]
    resolution_reason: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ScreeningPage:
    items: list[Screening]
    total: int
    limit: int
    offset: int


@strawberry.type
class CasePage:
    items: list[Case]
    total: int
    limit: int
    offset: int


# ============================================================
# GRAPHQL DATABASE STATUS EXPRESSION
# ============================================================

_EFFECTIVE_DECISION = func.coalesce(
    ComplianceAudit.decision,
    case(
        (
            ComplianceAudit.matched.is_(True)
            & (
                ComplianceAudit.match_score
                >= INTERNAL_BLOCK_MATCH_SCORE
            ),
            "BLOCK",
        ),
        (
            ComplianceAudit.matched.is_(True),
            "REVIEW",
        ),
        else_="CLEAR",
    ),
)


# ============================================================
# CONVERSION HELPERS
# ============================================================


def _screening_status(
    audit: ComplianceAudit,
) -> ScreeningStatus:
    decision = audit.decision

    if not decision:
        decision = compute_decision(
            matched=bool(audit.matched),
            match_score=float(
                audit.match_score or 0
            ),
        )

    return ScreeningStatus(decision)


def _case_status(
    case: ComplianceCase,
) -> CaseStatus:
    return CaseStatus(case.status)


def _to_screening(
    audit: ComplianceAudit,
) -> Screening:
    return Screening(
        id=audit.id,
        entity_name=audit.entity_name,
        country=audit.country,
        status=_screening_status(audit),
        matched=audit.matched,
        matched_name=audit.matched_name,
        matched_lists=audit.matched_lists,
        match_score=audit.match_score,
        risk_score=audit.risk_score,
        screening_type=audit.screening_type,
        newly_flagged=audit.newly_flagged,
        screening_run_id=audit.screening_run_id,
        duration_ms=audit.duration_ms,
        created_at=audit.created_at,
    )


def _to_case(
    case: ComplianceCase,
) -> Case:
    return Case(
        id=case.id,
        case_number=case.case_number,
        entity_name=case.entity_name,
        entity_type=case.entity_type,
        country=case.country,
        matched_name=case.matched_name,
        matched_lists=case.matched_lists,
        match_score=case.match_score,
        risk_score=case.risk_score,
        screening_tier=case.screening_tier,
        screening_action=case.screening_action,
        status=_case_status(case),
        assigned_to=case.assigned_to,
        assigned_at=case.assigned_at,
        resolution=case.resolution,
        resolution_reason=case.resolution_reason,
        resolved_at=case.resolved_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


# ============================================================
# GRAPHQL QUERY
# ============================================================


@strawberry.type
class Query:

    # ========================================================
    # SCREENINGS
    # ========================================================

    @strawberry.field
    def screenings(
        self,
        status: Optional[ScreeningStatus] = None,
        jurisdiction: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ScreeningPage:

        limit = max(
            1,
            min(limit, 100),
        )

        offset = max(
            0,
            offset,
        )

        db = SessionLocal()

        try:
            query = db.query(
                ComplianceAudit
            )

            # ------------------------------------------------
            # Status filter
            # ------------------------------------------------

            if status is not None:
                query = query.filter(
                    _EFFECTIVE_DECISION
                    == status.value
                )

            # ------------------------------------------------
            # Jurisdiction filter
            # ------------------------------------------------

            if jurisdiction is not None:
                normalized_jurisdiction = (
                    jurisdiction.strip()
                )

                if normalized_jurisdiction:
                    query = query.filter(
                        func.lower(
                            ComplianceAudit.country
                        )
                        == normalized_jurisdiction.lower()
                    )

            # ------------------------------------------------
            # Date range filter
            # ------------------------------------------------

            if date_from is not None:
                query = query.filter(
                    ComplianceAudit.created_at
                    >= date_from
                )

            if date_to is not None:
                query = query.filter(
                    ComplianceAudit.created_at
                    <= date_to
                )

            # ------------------------------------------------
            # Total matching records
            # ------------------------------------------------

            total = query.count()

            # ------------------------------------------------
            # Pagination
            # ------------------------------------------------

            records = (
                query
                .order_by(
                    ComplianceAudit.created_at.desc()
                )
                .offset(offset)
                .limit(limit)
                .all()
            )

            # ------------------------------------------------
            # Convert records
            # ------------------------------------------------

            items = [
                _to_screening(record)
                for record in records
            ]

            return ScreeningPage(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )

        finally:
            db.close()

    # ========================================================
    # CASES
    # ========================================================

    @strawberry.field
    def cases(
        self,
        status: Optional[CaseStatus] = None,
        jurisdiction: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CasePage:

        limit = max(
            1,
            min(limit, 100),
        )

        offset = max(
            0,
            offset,
        )

        db = SessionLocal()

        try:
            query = db.query(
                ComplianceCase
            )

            # ------------------------------------------------
            # Status filter
            # ------------------------------------------------

            if status is not None:
                query = query.filter(
                    ComplianceCase.status
                    == status.value
                )

            # ------------------------------------------------
            # Jurisdiction filter
            # ------------------------------------------------

            if jurisdiction is not None:
                normalized_jurisdiction = (
                    jurisdiction.strip()
                )

                if normalized_jurisdiction:
                    query = query.filter(
                        func.lower(
                            ComplianceCase.country
                        )
                        == normalized_jurisdiction.lower()
                    )

            # ------------------------------------------------
            # Date range filter
            # ------------------------------------------------

            if date_from is not None:
                query = query.filter(
                    ComplianceCase.created_at
                    >= date_from
                )

            if date_to is not None:
                query = query.filter(
                    ComplianceCase.created_at
                    <= date_to
                )

            # ------------------------------------------------
            # Total matching records
            # ------------------------------------------------

            total = query.count()

            # ------------------------------------------------
            # Pagination
            # ------------------------------------------------

            records = (
                query
                .order_by(
                    ComplianceCase.created_at.desc()
                )
                .offset(offset)
                .limit(limit)
                .all()
            )

            # ------------------------------------------------
            # Convert records
            # ------------------------------------------------

            items = [
                _to_case(record)
                for record in records
            ]

            return CasePage(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )

        finally:
            db.close()


# ============================================================
# GRAPHQL SCHEMA
# ============================================================


schema = strawberry.Schema(
    query=Query,
)