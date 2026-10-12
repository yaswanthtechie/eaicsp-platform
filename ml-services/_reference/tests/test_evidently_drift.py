"""
Milestone 2 Evidently drift tests.
"""

from pathlib import Path

from src.evidently_drift import (
    CLASS_NAMES,
    _prediction_to_value,
    add_predictions,
    calculate_evidently_drift,
    create_recent_inputs,
    create_shifted_inputs,
    generate_drift_report,
    load_reference_inputs,
)


def test_reference_data_has_four_features():
    reference = load_reference_inputs()

    assert len(reference) == 150
    assert list(reference.columns) == [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
    ]


def test_recent_data_has_same_schema():
    reference = load_reference_inputs()

    recent = create_recent_inputs(
        reference,
        sample_count=100,
    )

    assert len(recent) == 100
    assert list(recent.columns) == list(
        reference.columns
    )


def test_shifted_data_is_different():
    reference = load_reference_inputs()

    shifted = create_shifted_inputs(
        reference,
        shift=2.0,
    )

    assert len(shifted) == len(reference)

    assert not shifted.equals(reference)

    for column in reference.columns:
        assert (
            shifted[column].mean()
            > reference[column].mean()
        )


def test_evidently_report_is_generated(tmp_path: Path):
    reference = load_reference_inputs()

    shifted = create_shifted_inputs(
        reference,
        shift=2.0,
    )

    report_path = (
        tmp_path / "drift_report.html"
    )

    result = generate_drift_report(
        reference_data=reference,
        recent_data=shifted,
        report_path=report_path,
    )

    assert report_path.exists()
    assert report_path.stat().st_size > 0

    assert result["reference_samples"] == 150
    assert result["recent_samples"] == 150


# ------------------------------------------------------------------
# Evidently's verdict is used, and a deliberate shift is CAUGHT
# ------------------------------------------------------------------


def test_deliberate_shift_is_caught_by_evidently():
    reference = load_reference_inputs()

    result = calculate_evidently_drift(
        reference,
        create_shifted_inputs(reference),
    )

    assert result["data_drift_detected"] is True
    assert result["drifted_feature_share"] == 1.0
    assert result["prediction_drift_detected"] is True


def test_same_distribution_is_not_flagged():
    reference = load_reference_inputs()

    result = calculate_evidently_drift(
        reference,
        reference.copy(),
    )

    assert result["data_drift_detected"] is False
    assert result["prediction_drift_detected"] is False


def test_predictions_use_the_class_names_the_service_logs():
    labels = set(
        add_predictions(load_reference_inputs())[
            "prediction"
        ]
    )

    assert labels == set(CLASS_NAMES) == {
        "setosa",
        "versicolor",
        "virginica",
    }


def test_logged_class_index_is_mapped_to_its_name():
    assert _prediction_to_value("setosa") == "setosa"
    assert _prediction_to_value("2") == "virginica"
    assert (
        _prediction_to_value(
            '{"prediction": "versicolor"}'
        )
        == "versicolor"
    )


# ------------------------------------------------------------------
# Retraining trigger uses Evidently's verdicts and the configured threshold
# ------------------------------------------------------------------


def test_retraining_threshold_comes_from_config():
    from src import config, retraining

    assert (
        retraining.DRIFT_THRESHOLD
        == config.DRIFT_THRESHOLD
    )


def test_retraining_check_reads_evidently_verdicts(
    monkeypatch,
):
    import src.evidently_drift as evidently_drift
    from src.retraining import _run_evidently_check

    monkeypatch.setattr(
        evidently_drift,
        "calculate_logged_evidently_drift",
        lambda **kwargs: {
            "data_drift_detected": True,
            "prediction_drift_detected": False,
            "prediction_drift_p_value": 0.4,
            "drifted_feature_share": 0.75,
        },
    )

    result = _run_evidently_check(
        [[5.1, 3.5, 1.4, 0.2]]
    )

    assert result["data_drift_detected"] is True
    assert (
        result["prediction_drift_detected"]
        is False
    )
    assert result["drifted_feature_share"] == 0.75