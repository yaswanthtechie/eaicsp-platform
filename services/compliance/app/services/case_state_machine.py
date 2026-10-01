CASE_OPEN = "OPEN"
CASE_UNDER_REVIEW = "UNDER_REVIEW"
CASE_CLEARED = "CLEARED"
CASE_CONFIRMED = "CONFIRMED"


ALLOWED_TRANSITIONS = {
    CASE_OPEN: {
        CASE_UNDER_REVIEW,
    },
    CASE_UNDER_REVIEW: {
        CASE_CLEARED,
        CASE_CONFIRMED,
    },
    CASE_CLEARED: set(),
    CASE_CONFIRMED: set(),
}


def validate_transition(
    current_status: str,
    new_status: str,
) -> None:

    allowed_states = ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )

    if new_status not in allowed_states:
        raise ValueError(
            f"Invalid case state transition: "
            f"{current_status} -> {new_status}"
        )