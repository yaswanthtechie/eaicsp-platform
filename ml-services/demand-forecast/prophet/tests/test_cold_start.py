import pandas as pd
import pytest

from src.cold_start import (
    category_average_forecast,
    category_region_average_forecast,
    evaluate_all_skus,
    evaluate_cold_start,
    find_similar_skus,
)


@pytest.fixture
def sample_data():
    return pd.DataFrame(
        [
            # Electronics / South
            ["2025-01-01", "SKU001", "Electronics", "South", 100],
            ["2025-02-01", "SKU001", "Electronics", "South", 110],
            ["2025-03-01", "SKU001", "Electronics", "South", 120],
            ["2025-04-01", "SKU001", "Electronics", "South", 130],

            ["2025-01-01", "SKU002", "Electronics", "South", 200],
            ["2025-02-01", "SKU002", "Electronics", "South", 210],
            ["2025-03-01", "SKU002", "Electronics", "South", 220],
            ["2025-04-01", "SKU002", "Electronics", "South", 230],

            # Electronics / North
            ["2025-01-01", "SKU003", "Electronics", "North", 500],
            ["2025-02-01", "SKU003", "Electronics", "North", 510],
            ["2025-03-01", "SKU003", "Electronics", "North", 520],
            ["2025-04-01", "SKU003", "Electronics", "North", 530],

            # Grocery / South
            ["2025-01-01", "SKU004", "Grocery", "South", 50],
            ["2025-02-01", "SKU004", "Grocery", "South", 55],
            ["2025-03-01", "SKU004", "Grocery", "South", 60],
            ["2025-04-01", "SKU004", "Grocery", "South", 65],
        ],
        columns=[
            "date",
            "sku_id",
            "category",
            "region",
            "quantity_sold",
        ],
    )


def test_find_similar_skus_uses_category_and_region(sample_data):
    result = find_similar_skus(
        sample_data,
        category="Electronics",
        region="South",
    )

    assert result == ["SKU001", "SKU002"]


def test_find_similar_skus_excludes_target_sku(sample_data):
    result = find_similar_skus(
        sample_data,
        category="Electronics",
        region="South",
        exclude_sku_id="SKU001",
    )

    assert result == ["SKU002"]


def test_category_region_forecast(sample_data):
    forecast = category_region_average_forecast(
        sample_data,
        category="Electronics",
        region="South",
        horizon=2,
    )

    # Electronics / South demand:
    # (100+110+120+130+200+210+220+230) / 8 = 165
    assert forecast == [165.0, 165.0]


def test_category_region_forecast_requires_similar_sku(sample_data):
    with pytest.raises(ValueError, match="No similar SKUs"):
        category_region_average_forecast(
            sample_data,
            category="Electronics",
            region="West",
            horizon=2,
        )


def test_category_average_baseline(sample_data):
    forecast = category_average_forecast(
        sample_data,
        category="Electronics",
        horizon=2,
    )

    # Electronics demand:
    # SKU001 = 100+110+120+130 = 460
    # SKU002 = 200+210+220+230 = 860
    # SKU003 = 500+510+520+530 = 2060
    #
    # Total = 3380
    # Number of observations = 12
    # Average = 3380 / 12 = 281.666666...
    assert forecast == pytest.approx(
        [281.6666666666667, 281.6666666666667]
    )


def test_honest_cold_start_evaluation_excludes_target_history(sample_data):
    result = evaluate_cold_start(
        sample_data,
        sku_id="SKU001",
        hidden_periods=2,
    )

    assert result["sku_id"] == "SKU001"
    assert result["category"] == "Electronics"
    assert result["region"] == "South"

    assert result["actual"] == [120.0, 130.0]

    # SKU001 is excluded from the reference pool.
    # Only SKU002 remains as the Electronics / South reference SKU.
    assert result["cold_start_forecast"] == [205.0, 205.0]


def test_cold_start_hidden_history_is_chronological(sample_data):
    result = evaluate_cold_start(
        sample_data,
        sku_id="SKU002",
        hidden_periods=2,
    )

    assert result["actual"] == [220.0, 230.0]


def test_evaluate_all_skus(sample_data):
    results = evaluate_all_skus(
        sample_data,
        hidden_periods=2,
    )

    assert len(results) == 3

    assert {result["sku_id"] for result in results} == {
        "SKU001",
        "SKU002",
        "SKU003",
    }


def test_invalid_horizon(sample_data):
    with pytest.raises(ValueError, match="horizon"):
        category_region_average_forecast(
            sample_data,
            category="Electronics",
            region="South",
            horizon=0,
        )


def test_missing_required_column():
    bad_data = pd.DataFrame(
        {
            "sku_id": ["SKU001"],
            "category": ["Electronics"],
            "region": ["South"],
            "quantity_sold": [100],
        }
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        find_similar_skus(
            bad_data,
            category="Electronics",
            region="South",
        )


def test_evaluate_cold_start_reports_forecast_source(sample_data):
    result = evaluate_cold_start(
        sample_data,
        sku_id="SKU001",
        hidden_periods=3,
    )

    assert result["forecast_source"] == "category_region"
def test_cold_start_ignores_peer_demand_from_hidden_window():
    dates = pd.date_range(
        "2025-01-01",
        periods=6,
        freq="MS",
    )

    target = pd.DataFrame(
        {
            "date": dates,
            "sku_id": "T",
            "category": "C",
            "region": "R",
            "quantity_sold": [10] * 6,
        }
    )

    peer = pd.DataFrame(
        {
            "date": dates,
            "sku_id": "P",
            "category": "C",
            "region": "R",
            "quantity_sold": [
                20,
                20,
                20,
                9999,
                9999,
                9999,
            ],
        }
    )

    df = pd.concat(
        [target, peer],
        ignore_index=True,
    )

    result = evaluate_cold_start(
        df,
        sku_id="T",
        hidden_periods=3,
    )

    assert result["cold_start_forecast"] == pytest.approx(
        [20.0, 20.0, 20.0]
    )

    assert result["category_baseline"] == pytest.approx(
        [20.0, 20.0, 20.0]
    )    