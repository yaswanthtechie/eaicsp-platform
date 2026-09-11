import pytest

from app.services.case_state_machine import (
    validate_transition,
)


def test_open_to_under_review():
    validate_transition(
        "OPEN",
        "UNDER_REVIEW",
    )


def test_under_review_to_cleared():
    validate_transition(
        "UNDER_REVIEW",
        "CLEARED",
    )


def test_under_review_to_confirmed():
    validate_transition(
        "UNDER_REVIEW",
        "CONFIRMED",
    )


def test_open_to_cleared_is_invalid():

    with pytest.raises(ValueError):
        validate_transition(
            "OPEN",
            "CLEARED",
        )


def test_open_to_confirmed_is_invalid():

    with pytest.raises(ValueError):
        validate_transition(
            "OPEN",
            "CONFIRMED",
        )


def test_cleared_to_open_is_invalid():

    with pytest.raises(ValueError):
        validate_transition(
            "CLEARED",
            "OPEN",
        )


def test_confirmed_to_open_is_invalid():

    with pytest.raises(ValueError):
        validate_transition(
            "CONFIRMED",
            "OPEN",
        )