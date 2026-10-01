import pandas as pd

from feature_lib.feature_catalog import generate_eta_feature_catalog


def test_eta_feature_catalog_contains_expected_features():
    df = pd.DataFrame({
        "scheduled_pickup_date": ["2026-01-01", "2026-01-05"],
        "actual_pickup_date": ["2026-01-01", "2026-01-05"],
        "expected_delivery_date": ["2026-01-03", "2026-01-07"],
        "actual_delivery_date": ["2026-01-03", "2026-01-08"],
        "carrier_name": ["A", "A"],
        "route_id": ["R1", "R1"],
    })

    catalog = generate_eta_feature_catalog(df)

    assert "departure_day_of_week" in catalog["feature"].tolist()
    assert "historical_on_time_rate_carrier" in catalog["feature"].tolist()
    assert "historical_on_time_rate_route" in catalog["feature"].tolist()
    assert "historical_avg_transit_days_carrier_route" in catalog["feature"].tolist()
    assert (catalog["version"] == "eta-v1").all()


def test_eta_catalog_excludes_outcome_and_helper_columns():
    df = pd.DataFrame({
        "scheduled_pickup_date": ["2026-01-01"],
        "actual_pickup_date": ["2026-01-01"],
        "expected_delivery_date": ["2026-01-03"],
        "actual_delivery_date": ["2026-01-03"],
        "carrier_name": ["A"],
        "route_id": ["R1"],
    })

    catalog = generate_eta_feature_catalog(df)

    assert "is_on_time" not in catalog["feature"].tolist()
    assert "transit_days" not in catalog["feature"].tolist()
    assert "departure_time" not in catalog["feature"].tolist()