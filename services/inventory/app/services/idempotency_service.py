import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.idempotency import IdempotencyRecord

T = TypeVar("T")


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def compute_request_hash(payload: BaseModel | dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of a request body (excludes headers and secrets)."""
    raw_data = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    canonical = json.dumps(raw_data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_idempotency_key(idempotency_key: str | None) -> str | None:
    """Validate optional Idempotency-Key header value."""
    if idempotency_key is None:
        return None
    stripped = idempotency_key.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header cannot be empty",
        )
    if len(stripped) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header exceeds 128 characters",
        )
    return stripped


def _handle_existing_record(
    db: Session,
    existing: IdempotencyRecord,
    request_hash: str,
    now: datetime,
) -> JSONResponse | None:
    """
    Evaluate an existing idempotency record.
    Returns a replay JSONResponse if completed and valid, None if expired and purged,
    or raises 409 Conflict for hash mismatch or in-progress conflict.
    """
    if _as_utc(existing.expires_at) <= now:
        db.delete(existing)
        db.flush()
        return None

    if existing.status == "COMPLETED":
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key already used with a different request payload",
            )
        if existing.response_status_code is None or existing.response_body is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency record is incomplete",
            )
        return JSONResponse(
            status_code=existing.response_status_code,
            content=json.loads(existing.response_body),
        )

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Request with this Idempotency-Key is already in progress",
    )


def execute_idempotent(
    *,
    db: Session,
    idempotency_key: str | None,
    scope: str,
    request_payload: BaseModel | dict[str, Any],
    success_status_code: int,
    action: Callable[[], T],
    serialize: Callable[[T], Any],
    after_commit: Callable[[T], None] | None = None,
) -> T | JSONResponse:
    """
    Execute a mutating operation with optional database-backed idempotency.

    - If `idempotency_key` is None: runs `action()`, commits once, runs `after_commit`,
      and returns the domain result directly (preserving backward compatibility).
    - If `idempotency_key` is provided:
      - Replays cached response if `(key, scope)` is COMPLETED and not expired with matching hash.
      - Raises 409 Conflict if hash mismatches or another request is in progress.
      - Otherwise executes `action()`, records COMPLETED response, and commits both atomically.
      - Any exception in `action()` rolls back both business changes and the idempotency row.
    """
    key = normalize_idempotency_key(idempotency_key)
    if key is None:
        try:
            result = action()
            db.commit()
            if hasattr(result, "__table__"):
                db.refresh(result)
            if after_commit is not None:
                after_commit(result)
            return result
        except Exception:
            db.rollback()
            raise

    request_hash = compute_request_hash(request_payload)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.IDEMPOTENCY_RETENTION_SECONDS)

    try:
        existing = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.scope == scope,
            )
            .with_for_update()
            .first()
        )
        if existing is not None:
            replay = _handle_existing_record(db, existing, request_hash, now)
            if replay is not None:
                db.rollback()
                return replay

        record = IdempotencyRecord(
            idempotency_key=key,
            scope=scope,
            request_hash=request_hash,
            status="IN_PROGRESS",
            created_at=now,
            expires_at=expires_at,
        )
        db.add(record)

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            winner = (
                db.query(IdempotencyRecord)
                .filter(
                    IdempotencyRecord.idempotency_key == key,
                    IdempotencyRecord.scope == scope,
                )
                .with_for_update()
                .first()
            )
            if winner is not None:
                replay = _handle_existing_record(db, winner, request_hash, now)
                if replay is not None:
                    db.rollback()
                    return replay
                # Expired winner was purged inside _handle_existing_record; insert fresh row.
                record = IdempotencyRecord(
                    idempotency_key=key,
                    scope=scope,
                    request_hash=request_hash,
                    status="IN_PROGRESS",
                    created_at=now,
                    expires_at=expires_at,
                )
                db.add(record)
                db.flush()
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Concurrent idempotency conflict; retry request",
                ) from None

        result = action()
        db.flush()
        if hasattr(result, "__table__"):
            db.refresh(result)
        serialized = jsonable_encoder(serialize(result))
        record.status = "COMPLETED"
        record.response_status_code = success_status_code
        record.response_body = json.dumps(serialized, default=str)

        db.commit()
        if hasattr(result, "__table__"):
            db.refresh(result)
        if after_commit is not None:
            after_commit(result)
        return result

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
