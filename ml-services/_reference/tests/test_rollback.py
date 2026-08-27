from src.rollback import should_rollback


def test_rollback_when_new_model_is_worse():

    result = should_rollback(
        new_model_accuracy=0.70,
        previous_model_accuracy=0.92,
    )

    assert result is True


def test_no_rollback_when_new_model_is_better():

    result = should_rollback(
        new_model_accuracy=0.94,
        previous_model_accuracy=0.92,
    )

    assert result is False


def test_rollback_when_below_minimum_accuracy():

    result = should_rollback(
        new_model_accuracy=0.80,
        previous_model_accuracy=0.85,
        minimum_accuracy=0.85,
    )

    assert result is True