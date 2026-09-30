"""
Milestone 2 Evidently drift tests.
"""

from pathlib import Path

from src.evidently_drift import (
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