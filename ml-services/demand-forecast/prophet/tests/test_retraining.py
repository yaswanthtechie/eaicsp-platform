import pandas as pd
import pytest
import src.automated_retraining as retraining

from src.automated_retraining import (
    is_better_model,
    select_best_result,
    WEIGHT_GRID,
)

from src.hierarchy import (
    bottom_up_reconcile,
    verify_reconciliation,
)


# ============================================================
# R5 PROMOTION DECISION TESTS
# ============================================================

def test_better_model_is_promoted():
    """
    Better MAPE should result in promotion.
    """

    assert is_better_model(
        new_mape=2.0,
        new_rmse=100.0,
        old_mape=3.0,
        old_rmse=200.0,
    ) is True


def test_worse_model_is_rejected():
    """
    Worse MAPE should result in rejection.
    """

    assert is_better_model(
        new_mape=4.0,
        new_rmse=100.0,
        old_mape=3.0,
        old_rmse=200.0,
    ) is False


def test_equal_mape_uses_rmse():
    """
    When MAPE is tied, lower RMSE wins.
    """

    assert is_better_model(
        new_mape=3.0,
        new_rmse=100.0,
        old_mape=3.0,
        old_rmse=200.0,
    ) is True

    assert is_better_model(
        new_mape=3.0,
        new_rmse=300.0,
        old_mape=3.0,
        old_rmse=200.0,
    ) is False


# ============================================================
# R5 GRID SEARCH TESTS
# ============================================================

def test_all_11_ensemble_weights_are_present():
    """
    R5 must evaluate all 11 Prophet/XGBoost combinations.
    """

    assert len(WEIGHT_GRID) == 11

    for prophet_weight, xgb_weight in WEIGHT_GRID:
        assert prophet_weight + xgb_weight == pytest.approx(1.0)


def test_grid_search_selects_best_mape():
    """
    Lowest MAPE should be selected as the winner.
    """

    results = [
        {
            "prophet_weight": 0.0,
            "xgb_weight": 1.0,
            "mape": 3.0,
            "rmse": 100.0,
        },
        {
            "prophet_weight": 0.3,
            "xgb_weight": 0.7,
            "mape": 2.0,
            "rmse": 120.0,
        },
        {
            "prophet_weight": 0.8,
            "xgb_weight": 0.2,
            "mape": 2.5,
            "rmse": 80.0,
        },
    ]

    winner = select_best_result(results)

    assert winner["prophet_weight"] == 0.3
    assert winner["xgb_weight"] == 0.7
    assert winner["mape"] == 2.0


def test_grid_search_uses_rmse_as_tie_breaker():
    """
    If MAPE is equal, lower RMSE should win.
    """

    results = [
        {
            "prophet_weight": 0.2,
            "xgb_weight": 0.8,
            "mape": 2.0,
            "rmse": 150.0,
        },
        {
            "prophet_weight": 0.4,
            "xgb_weight": 0.6,
            "mape": 2.0,
            "rmse": 100.0,
        },
    ]

    winner = select_best_result(results)

    assert winner["prophet_weight"] == 0.4
    assert winner["xgb_weight"] == 0.6
    assert winner["rmse"] == 100.0


# ============================================================
# R5 3-LEVEL HIERARCHICAL RECONCILIATION
# ============================================================

def test_three_level_reconciliation_multiple_regions():
    """
    Verify:

        SKU -> Category -> Region

    across multiple dates and multiple regions.
    """

    sku_forecasts = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "sku_id": "SKU001",
                "predicted": 100.0,
            },
            {
                "date": "2026-01-01",
                "sku_id": "SKU002",
                "predicted": 150.0,
            },
            {
                "date": "2026-01-01",
                "sku_id": "SKU003",
                "predicted": 200.0,
            },
            {
                "date": "2026-01-01",
                "sku_id": "SKU004",
                "predicted": 50.0,
            },
            {
                "date": "2026-02-01",
                "sku_id": "SKU001",
                "predicted": 120.0,
            },
            {
                "date": "2026-02-01",
                "sku_id": "SKU002",
                "predicted": 180.0,
            },
            {
                "date": "2026-02-01",
                "sku_id": "SKU003",
                "predicted": 220.0,
            },
            {
                "date": "2026-02-01",
                "sku_id": "SKU004",
                "predicted": 80.0,
            },
        ]
    )

    hierarchy = pd.DataFrame(
        [
            {
                "sku_id": "SKU001",
                "category": "Clothing",
                "region": "North",
            },
            {
                "sku_id": "SKU002",
                "category": "Clothing",
                "region": "North",
            },
            {
                "sku_id": "SKU003",
                "category": "Electronics",
                "region": "South",
            },
            {
                "sku_id": "SKU004",
                "category": "Electronics",
                "region": "South",
            },
        ]
    )

    (
        sku_result,
        category_result,
        region_result,
    ) = bottom_up_reconcile(
        sku_forecasts,
        hierarchy,
    )

    # --------------------------------------------------------
    # Category totals
    # --------------------------------------------------------

    jan_clothing = category_result[
        (category_result["date"] == "2026-01-01")
        & (category_result["category"] == "Clothing")
    ]["predicted"].iloc[0]

    jan_electronics = category_result[
        (category_result["date"] == "2026-01-01")
        & (category_result["category"] == "Electronics")
    ]["predicted"].iloc[0]

    assert jan_clothing == pytest.approx(250.0)
    assert jan_electronics == pytest.approx(250.0)

    # --------------------------------------------------------
    # Region totals
    # --------------------------------------------------------

    jan_north = region_result[
        (region_result["date"] == "2026-01-01")
        & (region_result["region"] == "North")
    ]["predicted"].iloc[0]

    jan_south = region_result[
        (region_result["date"] == "2026-01-01")
        & (region_result["region"] == "South")
    ]["predicted"].iloc[0]

    assert jan_north == pytest.approx(250.0)
    assert jan_south == pytest.approx(250.0)

    # --------------------------------------------------------
    # Global consistency
    # --------------------------------------------------------

    assert sku_result["predicted"].sum() == pytest.approx(
        category_result["predicted"].sum()
    )

    assert category_result["predicted"].sum() == pytest.approx(
        region_result["predicted"].sum()
    )


# ============================================================
# R5 RECONCILIATION FAILURE PATH
# ============================================================

def test_verify_reconciliation_failure():
    """
    Intentionally introduce an incorrect category forecast.

    verify_reconciliation() must detect the mismatch.
    """

    sku_result = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "sku_id": "SKU001",
                "category": "Clothing",
                "region": "North",
                "predicted": 100.0,
            },
            {
                "date": "2026-01-01",
                "sku_id": "SKU002",
                "category": "Clothing",
                "region": "North",
                "predicted": 150.0,
            },
        ]
    )

    # Intentionally WRONG:
    # Correct category total = 250
    # We provide 300 to force failure.
    category_result = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "category": "Clothing",
                "region": "North",
                "predicted": 300.0,
            }
        ]
    )

    region_result = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "region": "North",
                "predicted": 300.0,
            }
        ]
    )

    with pytest.raises(
        AssertionError,
        match="SKU -> Category reconciliation failed",
    ):
        verify_reconciliation(
            sku_result,
            category_result,
            region_result,
        )


# ============================================================
# R5 MULTI-CYCLE RETRAINING TEST
# ============================================================

def test_multiple_retraining_cycles_execute(monkeypatch):
    """
    Verify that run_retraining() executes multiple yearly
    retraining cycles.
    """

    # --------------------------------------------------------
    # Fake dataset
    #
    # 156 monthly records = 13 years.
    # This is enough for multiple yearly triggers.
    # --------------------------------------------------------

    dates = pd.date_range(
        "2003-01-01",
        periods=156,
        freq="MS",
    )

    data = pd.DataFrame(
        {
            "ds": dates,
            "y": range(100, 256),
        }
    )

    # --------------------------------------------------------
    # Track executed yearly cycles
    # --------------------------------------------------------

    executed_cycles = []

    # --------------------------------------------------------
    # Prevent real promoted-model loading
    # --------------------------------------------------------

    monkeypatch.setattr(
        retraining,
        "load_existing_baseline",
        lambda: (
            float("inf"),
            float("inf"),
        ),
    )

    # --------------------------------------------------------
    # Replace actual expensive training cycle
    # --------------------------------------------------------

    def fake_retrain_once(
        data,
        trigger_date,
        old_mape,
        old_rmse,
    ):
        executed_cycles.append(
            trigger_date.year
        )

        cycle_number = len(
            executed_cycles
        )

        # Return an improving candidate
        # so the next cycle receives
        # the updated baseline.
        new_mape = 10.0 - cycle_number
        new_rmse = 1000.0 - (
            cycle_number * 10
        )

        return (
            new_mape,
            new_rmse,
        )

    monkeypatch.setattr(
        retraining,
        "retrain_once",
        fake_retrain_once,
    )

    # --------------------------------------------------------
    # Replace prepare_data so the test
    # does not depend on the real sales dataset.
    # --------------------------------------------------------

    monkeypatch.setattr(
        retraining,
        "prepare_data",
        lambda: data,
    )

    # --------------------------------------------------------
    # Execute automated retraining
    # --------------------------------------------------------

    retraining.run_retraining()

    # --------------------------------------------------------
    # Verify multiple cycles executed
    # --------------------------------------------------------

    assert len(executed_cycles) >= 2

    # Yearly triggers must be different years.
    assert executed_cycles[0] < executed_cycles[1]

    # Confirm at least two distinct cycles.
    assert len(set(executed_cycles)) >= 2
def test_rejected_cycle_does_not_advance_baseline(monkeypatch):
    #A rejected candidate must not become the next cycle's baseline#
    dates = pd.date_range("2003-01-01", periods=156, freq="MS")
    data = pd.DataFrame({"ds": dates, "y": range(100, 256)})

    seen_baselines = []

    monkeypatch.setattr(retraining, "prepare_data", lambda: data)
    monkeypatch.setattr(retraining, "load_existing_baseline", lambda: (5.0, 500.0))

    # Every candidate is worse than the 5.0 promoted baseline.
    def fake_retrain_once(data, trigger_date, old_mape, old_rmse):
        seen_baselines.append(old_mape)
        return 9.0, 900.0

    monkeypatch.setattr(retraining, "retrain_once", fake_retrain_once)
    retraining.run_retraining()

    # Every cycle must have compared against the ORIGINAL baseline (5.0),
    # never against the previous rejected candidate (9.0).
    assert set(seen_baselines) == {5.0}, seen_baselines