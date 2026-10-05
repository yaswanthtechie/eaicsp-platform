from datetime import datetime, timezone
from typing import Any
import logging
import threading
import time

from sqlalchemy.orm import Session

from app.services.sanctions_service import screen_entity
from app.services.sla_service import record_request, start_timer
from app.services.sla_alert_service import send_sla_alert
from app.core.config import (
    INTERNAL_BLOCK_MATCH_SCORE,
    SLA_ALERT_COOLDOWN_SECONDS,
    SLA_LATENCY_THRESHOLD_MS,
)


logger = logging.getLogger(__name__)


# ============================================================
# SLA ALERT COOLDOWN
# ============================================================

_LAST_SLA_ALERT_AT: float | None = None
_SLA_ALERT_LOCK = threading.Lock()


def _alert_sla_degraded(
    caller_service: str,
    supplier_id: str,
    latency_ms: float,
) -> bool:
    
    global _LAST_SLA_ALERT_AT

    now = time.monotonic()

    with _SLA_ALERT_LOCK:
        if (
            _LAST_SLA_ALERT_AT is not None
            and now - _LAST_SLA_ALERT_AT < SLA_ALERT_COOLDOWN_SECONDS
        ):
            return False

        _LAST_SLA_ALERT_AT = now

    threading.Thread(
        target=send_sla_alert,
        kwargs={
            "caller_service": caller_service,
            "supplier_id": supplier_id,
            "latency_ms": latency_ms,
            "threshold_ms": SLA_LATENCY_THRESHOLD_MS,
        },
        daemon=True,
    ).start()

    return True


# ============================================================
# INTERNAL COMPLIANCE CACHE
# ============================================================

_INTERNAL_CHECK_CACHE: dict[
    tuple[str, str, str],
    tuple[datetime, dict[str, Any]],
] = {}

_CACHE_LOCKS: dict[
    tuple[str, str, str],
    threading.Lock,
] = {}

_CACHE_LOCKS_GUARD = threading.Lock()

CACHE_TTL_SECONDS = 300

def clear_internal_cache() -> None:
    
    with _CACHE_LOCKS_GUARD:
        _INTERNAL_CHECK_CACHE.clear()

    logger.info("Internal compliance cache cleared")

# ============================================================
# CACHE METRICS
# ============================================================

_CACHE_HITS = 0
_CACHE_MISSES = 0

_CACHE_METRICS_LOCK = threading.Lock()


def _record_cache_hit() -> None:
    global _CACHE_HITS

    with _CACHE_METRICS_LOCK:
        _CACHE_HITS += 1


def _record_cache_miss() -> None:
    global _CACHE_MISSES

    with _CACHE_METRICS_LOCK:
        _CACHE_MISSES += 1


def get_cache_metrics() -> dict[str, float | int]:
    with _CACHE_METRICS_LOCK:
        total_requests = (
            _CACHE_HITS + _CACHE_MISSES
        )

        hit_rate = (
            (_CACHE_HITS / total_requests) * 100
            if total_requests > 0
            else 0.0
        )

        return {
            "cache_hits": _CACHE_HITS,
            "cache_misses": _CACHE_MISSES,
            "cache_hit_rate": round(
                hit_rate,
                2,
            ),
        }


# ============================================================
# CACHE KEY
# ============================================================

def _get_cache_key(
    supplier_id: str,
    company_name: str,
    country: str,
) -> tuple[str, str, str]:
    return (
        supplier_id.strip().upper(),
        company_name.strip().upper(),
        country.strip().upper(),
    )


# ============================================================
# GET CACHED RESULT
# ============================================================

def _get_cached_result(
    cache_key: tuple[str, str, str],
) -> dict[str, Any] | None:

    cached = _INTERNAL_CHECK_CACHE.get(
        cache_key
    )

    if cached is None:
        return None

    cached_at, result = cached

    age_seconds = (
        datetime.now(timezone.utc) - cached_at
    ).total_seconds()

    if age_seconds >= CACHE_TTL_SECONDS:
        _INTERNAL_CHECK_CACHE.pop(
            cache_key,
            None,
        )

        logger.debug(
            "Internal compliance cache expired: "
            "cache_key=%s",
            cache_key,
        )

        return None

    return result.copy()


# ============================================================
# CACHE RESULT
# ============================================================

def _cache_result(
    cache_key: tuple[str, str, str],
    result: dict[str, Any],
) -> None:

    _INTERNAL_CHECK_CACHE[cache_key] = (
        datetime.now(timezone.utc),
        result.copy(),
    )


# ============================================================
# CACHE LOCK
# ============================================================

def _get_cache_lock(
    cache_key: tuple[str, str, str],
) -> threading.Lock:

    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(
            cache_key
        )

        if lock is None:
            lock = threading.Lock()

            _CACHE_LOCKS[cache_key] = lock

        return lock


# ============================================================
# BUILD COMPLIANCE RESPONSE
# ============================================================

def _build_compliance_response(
    result: dict[str, Any],
    supplier_id: str,
    company_name: str,
    country: str,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # COMPLIANCE OVERRIDE
    # --------------------------------------------------------

    if result.get("override_applied"):
        return {
            "supplier_id": supplier_id,
            "company_name": company_name,
            "country": country,
            "cleared": True,
            "decision": "CLEAR",
            "reason": (
                "Supplier match was reviewed and "
                "approved by compliance."
            ),
        }

    # --------------------------------------------------------
    # NO MATCH
    # --------------------------------------------------------

    if not result.get("is_flagged"):
        return {
            "supplier_id": supplier_id,
            "company_name": company_name,
            "country": country,
            "cleared": True,
            "decision": "CLEAR",
            "reason": (
                "No sanctions or watchlist match found."
            ),
        }

    # --------------------------------------------------------
    # MATCH FOUND
    # --------------------------------------------------------

    match_score = float(
        result.get(
            "match_score",
            0,
        )
    )

    matched_lists = result.get(
        "matched_lists",
        [],
    )

    if not isinstance(
        matched_lists,
        list,
    ):
        matched_lists = [
            str(matched_lists)
        ]

    # --------------------------------------------------------
    # STRONG MATCH -> BLOCK
    # --------------------------------------------------------

    if match_score >= INTERNAL_BLOCK_MATCH_SCORE:

        sources = ", ".join(
            str(source)
            for source in matched_lists
        )

        reason = (
            "Strong compliance match found"
        )

        if sources:
            reason += f" on {sources}"

        return {
            "supplier_id": supplier_id,
            "company_name": company_name,
            "country": country,
            "cleared": False,
            "decision": "BLOCK",
            "reason": reason,
        }

    # --------------------------------------------------------
    # POSSIBLE MATCH -> REVIEW
    # --------------------------------------------------------

    return {
        "supplier_id": supplier_id,
        "company_name": company_name,
        "country": country,
        "cleared": False,
        "decision": "REVIEW",
        "reason": (
            "Potential compliance match requires "
            "human review."
        ),
    }


# ============================================================
# INTERNAL COMPLIANCE CHECK
# ============================================================

def perform_internal_compliance_check(
    db: Session,
    supplier_id: str,
    company_name: str,
    country: str,
    caller_service: str = "unknown",
) -> dict[str, Any]:

    logger.info(
        "Received internal compliance request: "
        "caller=%s supplier_id=%s "
        "company_name=%s country=%s",
        caller_service,
        supplier_id,
        company_name,
        country,
    )

    # --------------------------------------------------------
    # START SLA TIMER
    # --------------------------------------------------------

    sla_start_time = start_timer()

    # --------------------------------------------------------
    # CREATE CACHE KEY
    # --------------------------------------------------------

    cache_key = _get_cache_key(
        supplier_id=supplier_id,
        company_name=company_name,
        country=country,
    )

    # --------------------------------------------------------
    # CHECK CACHE
    # --------------------------------------------------------

    cached_result = _get_cached_result(
        cache_key
    )

    if cached_result is not None:

        _record_cache_hit()

        logger.info(
            "Internal compliance check cache hit: "
            "caller=%s supplier_id=%s "
            "company_name=%s country=%s",
            caller_service,
            supplier_id,
            company_name,
            country,
        )

        duration_ms = record_request(
            start_time=sla_start_time,
            success=True,
        )

        logger.info(
            "Internal compliance SLA recorded: "
            "caller=%s supplier_id=%s "
            "cache_hit=true duration_ms=%.2f",
            caller_service,
            supplier_id,
            duration_ms,
        )

        return cached_result

    # --------------------------------------------------------
    # CACHE MISS
    # --------------------------------------------------------

    _record_cache_miss()

    cache_lock = _get_cache_lock(
        cache_key
    )

    # --------------------------------------------------------
    # PREVENT DUPLICATE SCREENING
    # --------------------------------------------------------

    with cache_lock:

        cached_result = _get_cached_result(
            cache_key
        )

        if cached_result is not None:

            _record_cache_hit()

            logger.info(
                "Internal compliance check cache hit "
                "after lock: caller=%s "
                "supplier_id=%s company_name=%s "
                "country=%s",
                caller_service,
                supplier_id,
                company_name,
                country,
            )

            duration_ms = record_request(
                start_time=sla_start_time,
                success=True,
            )

            logger.info(
                "Internal compliance SLA recorded: "
                "caller=%s supplier_id=%s "
                "cache_hit=true duration_ms=%.2f",
                caller_service,
                supplier_id,
                duration_ms,
            )

            return cached_result

        # ----------------------------------------------------
        # START COMPLIANCE CHECK
        # ----------------------------------------------------

        started_at = datetime.now(
            timezone.utc
        )

        logger.info(
            "Internal compliance check started: "
            "caller=%s supplier_id=%s "
            "company_name=%s country=%s time=%s",
            caller_service,
            supplier_id,
            company_name,
            country,
            started_at.isoformat(),
        )

        try:

            # ------------------------------------------------
            # SCREEN SUPPLIER
            # ------------------------------------------------

            result = screen_entity(
                name=company_name,
                country=country,
                db=db,
            )

            # ------------------------------------------------
            # BUILD SIMPLE INTERNAL RESPONSE
            # ------------------------------------------------

            response = _build_compliance_response(
                result=result,
                supplier_id=supplier_id,
                company_name=company_name,
                country=country,
            )

            # ------------------------------------------------
            # CACHE RESPONSE
            # ------------------------------------------------

            _cache_result(
                cache_key=cache_key,
                result=response,
            )

            # ------------------------------------------------
            # CALCULATE LATENCY
            # ------------------------------------------------

            completed_at = datetime.now(
                timezone.utc
            )

            duration_ms = (
                completed_at - started_at
            ).total_seconds() * 1000

            # ------------------------------------------------
            # RECORD SLA
            # ------------------------------------------------

            sla_duration_ms = record_request(
                start_time=sla_start_time,
                success=True,
            )

            # ------------------------------------------------
            # SUCCESS LOG
            # ------------------------------------------------

            logger.info(
                "Internal compliance check completed: "
                "caller=%s supplier_id=%s "
                "company_name=%s decision=%s "
                "cleared=%s duration_ms=%.2f "
                "sla_duration_ms=%.2f time=%s",
                caller_service,
                supplier_id,
                company_name,
                response["decision"],
                response["cleared"],
                duration_ms,
                sla_duration_ms,
                completed_at.isoformat(),
            )

            # ------------------------------------------------
            # SLA ALERT
            # ------------------------------------------------

            if (
                duration_ms
                > SLA_LATENCY_THRESHOLD_MS
            ):

                logger.warning(
                    "Compliance SLA degraded: "
                    "caller=%s supplier_id=%s "
                    "company_name=%s "
                    "latency=%.2fms threshold=%dms",
                    caller_service,
                    supplier_id,
                    company_name,
                    duration_ms,
                    SLA_LATENCY_THRESHOLD_MS,
                )

                
                _alert_sla_degraded(
                    caller_service=caller_service,
                    supplier_id=supplier_id,
                    latency_ms=duration_ms,
                )

            return response

        except Exception:

            # ------------------------------------------------
            # RECORD FAILED REQUEST
            # ------------------------------------------------

            duration_ms = record_request(
                start_time=sla_start_time,
                success=False,
            )

            logger.exception(
                "Internal compliance check failed: "
                "caller=%s supplier_id=%s "
                "company_name=%s duration_ms=%.2f",
                caller_service,
                supplier_id,
                company_name,
                duration_ms,
            )

            raise