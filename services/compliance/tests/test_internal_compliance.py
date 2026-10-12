from unittest.mock import patch
import time
from concurrent.futures import ThreadPoolExecutor

from app.core.database import SessionLocal
from app.services.internal_compliance_service import (
    _INTERNAL_CHECK_CACHE,
    perform_internal_compliance_check,
)


def get_db():
    db = SessionLocal()

    try:
        return db
    except Exception:
        db.close()
        raise


def clear_cache():
    _INTERNAL_CHECK_CACHE.clear()


def test_clean_supplier_returns_clear():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": False,
                "override_applied": False,
            }

            result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-001",
                company_name="ABC Supplies",
                country="India",
                caller_service="supplier-portal",
            )

        assert result["cleared"] is True
        assert result["decision"] == "CLEAR"
        assert "No sanctions" in result["reason"]

    finally:
        db.close()


def test_strong_match_returns_block():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": True,
                "override_applied": False,
                "match_score": 100,
                "matched_lists": ["OFAC", "EU"],
            }

            result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-002",
                company_name="HAMAS",
                country="India",
                caller_service="supplier-portal",
            )

        assert result["cleared"] is False
        assert result["decision"] == "BLOCK"
        assert "OFAC" in result["reason"]
        assert "EU" in result["reason"]

    finally:
        db.close()


def test_ambiguous_match_returns_review():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": True,
                "override_applied": False,
                "match_score": 87,
                "matched_lists": ["OFAC"],
            }

            result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-003",
                company_name="Possible Match",
                country="India",
                caller_service="supplier-portal",
            )

        assert result["cleared"] is False
        assert result["decision"] == "REVIEW"
        assert "human review" in result["reason"]

    finally:
        db.close()


def test_override_returns_clear():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": True,
                "override_applied": True,
                "match_score": 100,
                "matched_lists": ["OFAC"],
            }

            result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-004",
                company_name="Approved Supplier",
                country="India",
                caller_service="supplier-portal",
            )

        assert result["cleared"] is True
        assert result["decision"] == "CLEAR"

    finally:
        db.close()


def test_repeated_supplier_check_uses_cache():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": False,
                "override_applied": False,
            }

            first_result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-CACHE-001",
                company_name="Cached Supplier",
                country="India",
                caller_service="supplier-portal",
            )

            second_result = perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-CACHE-001",
                company_name="Cached Supplier",
                country="India",
                caller_service="supplier-portal",
            )

        assert first_result == second_result
        assert mock_screen.call_count == 1

    finally:
        db.close()


def test_different_suppliers_do_not_share_cache():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:
            mock_screen.return_value = {
                "is_flagged": False,
                "override_applied": False,
            }

            perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-CACHE-001",
                company_name="Supplier One",
                country="India",
                caller_service="supplier-portal",
            )

            perform_internal_compliance_check(
                db=db,
                supplier_id="SUP-CACHE-002",
                company_name="Supplier Two",
                country="India",
                caller_service="supplier-portal",
            )

        assert mock_screen.call_count == 2

    finally:
        db.close()


def test_concurrent_same_supplier_check_runs_screening_once():
    clear_cache()
    db = get_db()

    try:
        with patch(
            "app.services.internal_compliance_service.screen_entity"
        ) as mock_screen:

            def slow_screen(*args, **kwargs):
                time.sleep(0.1)

                return {
                    "is_flagged": False,
                    "override_applied": False,
                    "match_score": 0,
                    "matched_lists": [],
                }

            mock_screen.side_effect = slow_screen

            def make_request():
                return perform_internal_compliance_check(
                    db=db,
                    supplier_id="SUP-CONCURRENT-001",
                    company_name="Concurrent Supplier",
                    country="India",
                    caller_service="supplier-portal",
                )

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(make_request)
                    for _ in range(5)
                ]

                results = [
                    future.result()
                    for future in futures
                ]

        assert len(results) == 5

        for result in results:
            assert result["decision"] == "CLEAR"
            assert result["cleared"] is True

        assert mock_screen.call_count == 1

    finally:
        db.close()