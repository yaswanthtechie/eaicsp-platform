
import pandas as pd
import pytest

from src.client_evaluate import (
    evaluate_client_predictions,
    evaluate_client_baseline,
)


def sample_data():
    y_true = pd.Series([4.0, 3.0, 5.0, 6.0])

    metadata = pd.DataFrame(
        {
            "carrier_name": [
                "Carrier A",
                "Carrier B",
                "Carrier A",
                "Carrier B",
            ],
            "planned_delivery_days": [3.0, 4.0, 5.0, 8.0],
        }
    )

    return y_true, metadata


def test_evaluates_planned_delivery_baseline():
    y_true, metadata = sample_data()

    result = evaluate_client_baseline(y_true, metadata)

    assert result["mae_days"] == pytest.approx(1.0)
    assert result["evaluated_shipments"] == 4
    assert result["excluded_shipments"] == 0


def test_calculates_per_carrier_mae():
    y_true, metadata = sample_data()

    result = evaluate_client_baseline(y_true, metadata)

    assert result["per_carrier_mae"]["Carrier A"] == pytest.approx(0.5)
    assert result["per_carrier_mae"]["Carrier B"] == pytest.approx(1.5)


def test_excludes_missing_planned_baseline():
    y_true, metadata = sample_data()
    metadata.loc[0, "planned_delivery_days"] = None

    result = evaluate_client_baseline(y_true, metadata)

    assert result["evaluated_shipments"] == 3
    assert result["excluded_shipments"] == 1


def test_evaluates_model_predictions():
    y_true, metadata = sample_data()
    predictions = pd.Series([4.5, 3.5, 4.5, 5.5])

    result = evaluate_client_predictions(
        y_true, predictions, metadata
    )

    assert result["mae_days"] == pytest.approx(0.5)
    assert result["evaluated_shipments"] == 4


def test_rejects_mismatched_lengths():
    y_true, metadata = sample_data()

    with pytest.raises(ValueError, match="equal lengths"):
        evaluate_client_baseline(y_true.iloc[:-1], metadata)



import pandas as pd
import pytest

from src.client_evaluate import (
    compare_client_baseline_and_model,
)


def test_comparison_uses_same_shipments_for_both_mae():
    y_true = pd.Series([5.0, 6.0, 7.0, 8.0])

    predictions = pd.Series([5.5, float("nan"), 7.5, 8.5])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "A", "B", "B"],
        "planned_delivery_days": [6.0, 6.0, float("nan"), 9.0],
    })

    result = compare_client_baseline_and_model(
        y_true, predictions, metadata
    )

    # Only shipment 1 and shipment 4 are valid for both evaluations.
    assert result["evaluated_shipments"] == 2
    assert result["excluded_shipments"] == 2

    assert result["model_mae_days"] == pytest.approx(0.5)
    assert result["baseline_mae_days"] == pytest.approx(1.0)


def test_model_beats_baseline():
    y_true = pd.Series([5.0, 7.0, 9.0])

    predictions = pd.Series([5.2, 7.2, 9.2])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "B", "A"],
        "planned_delivery_days": [7.0, 9.0, 11.0],
    })

    result = compare_client_baseline_and_model(
        y_true, predictions, metadata
    )

    assert result["model_beats_baseline"] is True
    assert result["improvement_days"] > 0


def test_model_does_not_beat_baseline():
    y_true = pd.Series([5.0, 7.0, 9.0])

    predictions = pd.Series([8.0, 10.0, 12.0])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "B", "A"],
        "planned_delivery_days": [5.5, 7.5, 9.5],
    })

    result = compare_client_baseline_and_model(
        y_true, predictions, metadata
    )

    assert result["model_beats_baseline"] is False
    assert result["improvement_days"] < 0


def test_comparison_reports_model_per_carrier_mae():
    y_true = pd.Series([5.0, 7.0, 9.0, 11.0])

    predictions = pd.Series([6.0, 8.0, 10.0, 13.0])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "B", "A", "B"],
        "planned_delivery_days": [6.0, 8.0, 10.0, 12.0],
    })

    result = compare_client_baseline_and_model(
        y_true, predictions, metadata
    )

    assert result["model_per_carrier_mae"]["A"] == pytest.approx(1.0)
    assert result["model_per_carrier_mae"]["B"] == pytest.approx(1.5)


def test_comparison_rejects_no_common_valid_shipments():
    y_true = pd.Series([5.0, 6.0])

    predictions = pd.Series([float("nan"), float("nan")])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "B"],
        "planned_delivery_days": [5.0, 6.0],
    })

    with pytest.raises(ValueError, match="No common valid shipments"):
        compare_client_baseline_and_model(
            y_true, predictions, metadata
        )


def test_comparison_rejects_missing_baseline_column():
    y_true = pd.Series([5.0, 6.0])
    predictions = pd.Series([5.5, 6.5])

    metadata = pd.DataFrame({
        "carrier_name": ["A", "B"],
    })

    with pytest.raises(ValueError, match="planned_delivery_days"):
        compare_client_baseline_and_model(
            y_true, predictions, metadata
        )
