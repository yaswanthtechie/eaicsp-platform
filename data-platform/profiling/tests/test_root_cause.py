import pandas as pd

from src.root_cause import suggest_root_causes


def test_suggest_root_causes_with_strong_relationship():
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "quantity_sold": [50, 60, 80],
        }
    )

    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "quantity_sold": [25, 35, 40],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [100, 110, 120],
        }
    )

    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [130, 150, 160],
        }
    )

    relationships = [
        {
            "left_column": "sku_id",
            "right_column": "sku_id",
            "overlap_percentage": 100.0,
            "classification": "likely_join_key",
        }
    ]

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=relationships,
    )

    assert result

    candidate = result[0]

    assert candidate["downstream_metric"] == "quantity_sold"
    assert candidate["upstream_metric"] == "price"
    assert candidate["matched_keys"] == 3
    assert abs(candidate["correlation"]) >= 0.5
    assert "plausible contributing factor" in candidate["suggestion"]

def test_no_root_cause_when_upstream_does_not_drift():
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "quantity_sold": [50, 60, 80],
        }
    )

    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "quantity_sold": [25, 35, 40],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [100, 110, 120],
        }
    )

    # Upstream price unchanged
    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [100, 110, 120],
        }
    )

    relationships = [
        {
            "left_column": "sku_id",
            "right_column": "sku_id",
            "overlap_percentage": 100.0,
            "classification": "likely_join_key",
        }
    ]

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=relationships,
    )

    assert result == []

def test_no_root_cause_with_weak_association():
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4],
            "quantity_sold": [50, 60, 70, 80],
        }
    )

    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4],
            "quantity_sold": [100, 10, 90, 30],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4],
            "price": [100, 110, 120, 130],
        }
    )

    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4],
            "price": [105, 160, 125, 140],
        }
    )

    relationships = [
        {
            "left_column": "sku_id",
            "right_column": "sku_id",
            "overlap_percentage": 100.0,
            "classification": "likely_join_key",
        }
    ]

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=relationships,
    )

    assert result == []

def test_invalid_downstream_input():
    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [100, 110, 120],
        }
    )

    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3],
            "price": [120, 130, 140],
        }
    )

    relationships = [
        {
            "left_column": "sku_id",
            "right_column": "sku_id",
            "overlap_percentage": 100.0,
            "classification": "likely_join_key",
        }
    ]

    try:
        suggest_root_causes(
            downstream_old="invalid",
            downstream_new="invalid",
            upstream_old=upstream_old,
            upstream_new=upstream_new,
            relationships=relationships,
        )
        assert False, "Expected TypeError"
    except TypeError as exc:
        assert "downstream_old" in str(exc)


def test_multiple_root_cause_candidates_are_returned():
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "quantity_sold": [50, 60, 70, 80, 90],
        }
    )

    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "quantity_sold": [40, 42, 47, 52, 54],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "price": [100, 110, 120, 130, 140],
            "discount": [10, 11, 12, 13, 14],
        }
    )

    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "price": [120, 143, 150, 175.5, 196],
            "discount": [12, 14.3, 15, 17.55, 19.6],
        }
    )

    relationships = [
        {
            "left_column": "sku_id",
            "right_column": "sku_id",
            "overlap_percentage": 100.0,
            "classification": "likely_join_key",
        }
    ]

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=relationships,
    )

    assert len(result) == 2

    metrics = {
        candidate["upstream_metric"]
        for candidate in result
    }

    assert metrics == {"price", "discount"}

    assert all(
        abs(candidate["correlation"]) >= 0.5
        for candidate in result
    )