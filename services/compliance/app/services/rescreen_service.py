from __future__ import annotations

from datetime import datetime, timezone
import inspect
import time
from typing import Any

from app.core.database import SessionLocal
from app.models.audit import ComplianceAudit
from app.services.audit_service import write_audit
from app.services.sanctions_service import (
    apply_override,
    refresh_sanctions_data,
    screen_entity,
)


def generate_screening_run_id() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H-%M-%SZ"
    )


def get_latest_audits(
    db,
) -> dict[str, ComplianceAudit]:
    records = (
        db.query(ComplianceAudit)
        .order_by(
            ComplianceAudit.created_at.desc(),
            ComplianceAudit.id.desc(),
        )
        .all()
    )

    latest: dict[str, ComplianceAudit] = {}

    for record in records:
        entity_name = record.entity_name or ""
        entity_key = entity_name.strip().upper()

        if not entity_key:
            continue

        if entity_key not in latest:
            latest[entity_key] = record

    return latest


def get_previously_cleared_entities(
    db,
) -> list[ComplianceAudit]:
    latest_records = get_latest_audits(db)

    return [
        record
        for record in latest_records.values()
        if record.matched is False
    ]


def get_previous_cleared_entities(
    db,
) -> list[ComplianceAudit]:
    return get_previously_cleared_entities(db)


def _screen_entity_for_rescreen(
    entity_name: str,
    country: str | None,
    db,
) -> dict[str, Any]:
    parameters = inspect.signature(screen_entity).parameters

    kwargs: dict[str, Any] = {}

    if "country" in parameters:
        kwargs["country"] = country

    if "db" in parameters:
        kwargs["db"] = db

    return screen_entity(
        entity_name,
        **kwargs,
    )


def rescreen_entity(
    db,
    entity,
    screening_run_id: str | None = None,
) -> dict[str, Any]:
    if screening_run_id is None:
        screening_run_id = generate_screening_run_id()

    entity_name = entity.entity_name or ""
    country = entity.country

    start = time.perf_counter()

    result = _screen_entity_for_rescreen(
        entity_name=entity_name,
        country=country,
        db=db,
    )

    duration_ms = (
        time.perf_counter() - start
    ) * 1000

    result = apply_override(
        db=db,
        entity_name=entity_name,
        result=result,
    )

    if not result.get("country"):
        result["country"] = country

    is_flagged = bool(
        result.get(
            "is_flagged",
            False,
        )
    )

    risk_score = result.get(
        "risk_score",
        0,
    )

    risk_factors = result.get(
        "risk_factors",
        {},
    )

    if not is_flagged:
        return {
            "entity_name": entity_name,
            "previously_cleared": True,
            "newly_flagged": False,
            "screening_type": "RESCREEN",
            "screening_run_id": screening_run_id,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "result": result,
            "duration_ms": round(
                duration_ms,
                2,
            ),
        }

    result["screening_type"] = "RESCREEN"
    result["newly_flagged"] = True
    result["screening_run_id"] = screening_run_id
    result["risk_score"] = risk_score
    result["risk_factors"] = risk_factors

    write_audit(
        db=db,
        entity_name=entity_name,
        result=result,
        duration_ms=duration_ms,
        screening_type="RESCREEN",
        newly_flagged=True,
        screening_run_id=screening_run_id,
    )

    return {
        "entity_name": entity_name,
        "previously_cleared": True,
        "newly_flagged": True,
        "screening_type": "RESCREEN",
        "screening_run_id": screening_run_id,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "result": result,
        "duration_ms": round(
            duration_ms,
            2,
        ),
    }


def rescreen_cleared_entities() -> dict[str, Any]:
    job_start = time.perf_counter()

    screening_run_id = generate_screening_run_id()

    db = SessionLocal()

    try:
        refresh_sanctions_data()

        cleared_entities = get_previously_cleared_entities(db)

        total_checked = len(cleared_entities)

        print(
            "Previously-cleared entities: "
            f"{total_checked}"
        )

        newly_flagged = 0
        still_clean = 0

        results: list[dict[str, Any]] = []

        for entity in cleared_entities:
            result = rescreen_entity(
                db=db,
                entity=entity,
                screening_run_id=screening_run_id,
            )

            results.append(result)

            if result["newly_flagged"]:
                newly_flagged += 1
            else:
                still_clean += 1

        db.commit()

        total_duration_ms = (
            time.perf_counter() - job_start
        ) * 1000

        return {
            "screening_run_id": screening_run_id,
            "screening_type": "RESCREEN",
            "total_checked": total_checked,
            "newly_flagged": newly_flagged,
            "still_clean": still_clean,
            "total_duration_ms": round(
                total_duration_ms,
                2,
            ),
            "results": results,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def nightly_rescreen_job() -> dict[str, Any]:
    print("Starting nightly re-screen...")

    result = rescreen_cleared_entities()

    print(
        "Re-screen completed: "
        f"{result.get('total_checked', 0)} checked, "
        f"{result.get('newly_flagged', 0)} newly flagged, "
        f"{result.get('still_clean', 0)} still clean."
    )

    return result


if __name__ == "__main__":
    nightly_rescreen_job()