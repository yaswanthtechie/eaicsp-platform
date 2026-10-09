import pandas as pd

from src.compare import compare
from src.root_cause import MIN_MATCHED_KEYS, suggest_root_causes


SKU_RELATIONSHIP = [
    {
        "left_column": "sku_id",
        "right_column": "sku_id",
        "overlap_percentage": 100.0,
        "classification": "likely_join_key",
    }
]

def test_suggest_root_causes_with_strong_relationship():
    # 5 SKUs (the minimum). Price rises +10/+20/+30/+40/+50% and
    # quantity falls -5/-10/-15/-20/-25% for the same SKUs, so the
    # key-level changes are perfectly (negatively) associated.
    # Old values are close together so compare() sees the mean shift
    # as drift (it needs a shift larger than one old std deviation).
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "quantity_sold": [100, 101, 102, 103, 104],
        }
    )

    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "quantity_sold": [95.0, 90.9, 86.7, 82.4, 78.0],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "price": [100, 101, 102, 103, 104],
        }
    )

    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5],
            "price": [110.0, 121.2, 132.6, 144.2, 156.0],
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
    assert candidate["matched_keys"] == 5
    assert candidate["correlation"] == -1.0
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

def test_two_keys_are_never_enough_for_a_root_cause():
    """
    With 2 keys a correlation is always exactly +1 or -1, so it proves
    nothing. Below MIN_MATCHED_KEYS no suggestion may be made.
    """
    assert MIN_MATCHED_KEYS > 2

    downstream_old = pd.DataFrame(
        {"sku_id": [1, 2], "quantity_sold": [100, 101]}
    )
    downstream_new = pd.DataFrame(
        {"sku_id": [1, 2], "quantity_sold": [90.0, 60.6]}
    )
    upstream_old = pd.DataFrame(
        {"sku_id": [1, 2], "price": [100, 101]}
    )
    upstream_new = pd.DataFrame(
        {"sku_id": [1, 2], "price": [110.0, 141.4]}
    )

    # Both sides really drifted, so an empty result is because of the
    # key count, not because nothing happened.
    drifted = {"minor_drift", "major_drift"}
    assert (
        compare(downstream_old, downstream_new)["column_drift"]
        ["quantity_sold"]["status"] in drifted
    )
    assert (
        compare(upstream_old, upstream_new)["column_drift"]
        ["price"]["status"] in drifted
    )

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=SKU_RELATIONSHIP,
    )

    assert result == []

def test_unrelated_upstream_change_is_not_blamed():
    """
    Negative control: price AND quantity both drift, but the SKUs whose
    price rose most are not the ones whose sales fell most. Price must
    NOT be suggested as the cause just because both columns moved.
    """
    downstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5, 6],
            "quantity_sold": [100, 101, 102, 103, 104, 105],
        }
    )

    # Quantity changes: -10, -30, -30, -10, -20, -20 %
    downstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5, 6],
            "quantity_sold": [90.0, 70.7, 71.4, 92.7, 83.2, 84.0],
        }
    )

    upstream_old = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5, 6],
            "price": [100, 101, 102, 103, 104, 105],
        }
    )

    # Price changes: +10, +10, +50, +50, +30, +30 %  (correlation 0)
    upstream_new = pd.DataFrame(
        {
            "sku_id": [1, 2, 3, 4, 5, 6],
            "price": [110.0, 111.1, 153.0, 154.5, 135.2, 136.5],
        }
    )

    # Prove both sides really drifted, so an empty result means
    # "not related", not "nothing happened".
    drifted = {"minor_drift", "major_drift"}
    assert (
        compare(downstream_old, downstream_new)["column_drift"]
        ["quantity_sold"]["status"] in drifted
    )
    assert (
        compare(upstream_old, upstream_new)["column_drift"]
        ["price"]["status"] in drifted
    )

    result = suggest_root_causes(
        downstream_old=downstream_old,
        downstream_new=downstream_new,
        upstream_old=upstream_old,
        upstream_new=upstream_new,
        relationships=SKU_RELATIONSHIP,
    )

    assert result == []