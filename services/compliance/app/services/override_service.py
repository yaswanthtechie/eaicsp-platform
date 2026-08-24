from sqlalchemy.orm import Session

from app.models.compliance_override import ComplianceOverride


def normalize_override_name(entity_name: str) -> str:
    return " ".join(
        entity_name.strip().upper().split()
    )


def normalize_source(source: str) -> str:
    return source.strip().upper()


def create_override(
    db: Session,
    entity_name: str,
    matched_name: str,
    source: str,
    reason: str,
    reviewed_by: str,
):
    normalized_entity = normalize_override_name(
        entity_name
    )

    normalized_match = normalize_override_name(
        matched_name
    )

    normalized_source = normalize_source(
        source
    )

    existing = (
        db.query(ComplianceOverride)
        .filter(
            ComplianceOverride.entity_name
            == normalized_entity,

            ComplianceOverride.matched_name
            == normalized_match,

            ComplianceOverride.source
            == normalized_source,
        )
        .first()
    )

    if existing:
        existing.reason = reason
        existing.reviewed_by = reviewed_by

        db.commit()
        db.refresh(existing)

        return existing

    override = ComplianceOverride(
        entity_name=normalized_entity,
        matched_name=normalized_match,
        source=normalized_source,
        reason=reason,
        reviewed_by=reviewed_by,
    )

    db.add(override)
    db.commit()
    db.refresh(override)

    return override


def get_override(
    db: Session,
    entity_name: str,
    matched_name: str,
    source: str,
):
    normalized_entity = normalize_override_name(
        entity_name
    )

    normalized_match = normalize_override_name(
        matched_name
    )

    normalized_source = normalize_source(
        source
    )

    return (
        db.query(ComplianceOverride)
        .filter(
            ComplianceOverride.entity_name
            == normalized_entity,

            ComplianceOverride.matched_name
            == normalized_match,

            ComplianceOverride.source
            == normalized_source,
        )
        .first()
    )


def get_all_overrides(
    db: Session,
):
    return (
        db.query(ComplianceOverride)
        .order_by(
            ComplianceOverride.created_at.desc()
        )
        .all()
    )


def delete_override(
    db: Session,
    entity_name: str,
    matched_name: str,
    source: str,
):
    override = get_override(
        db=db,
        entity_name=entity_name,
        matched_name=matched_name,
        source=source,
    )

    if not override:
        return False

    db.delete(override)
    db.commit()

    return True