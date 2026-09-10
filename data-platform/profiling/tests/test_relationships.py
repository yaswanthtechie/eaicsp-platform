import pandas as pd
import pytest

from src.relationships import (
    calculate_overlap,
    discover_relationships,
)


def test_calculate_overlap():
    left = pd.Series(
        ["A", "B", "C", "D"]
    )

    right = pd.Series(
        ["A", "B", "C", "E"]
    )

    result = calculate_overlap(
        left,
        right,
    )

    # 3 common values / 4 values in smaller set = 75%
    assert result == pytest.approx(75.0)


def test_calculate_overlap_uses_unique_values():
    left = pd.Series(
        ["A", "A", "A", "B", "C", "D"]
    )

    right = pd.Series(
        ["A", "B", "C", "E"]
    )

    result = calculate_overlap(
        left,
        right,
    )

    # Unique left  = A, B, C, D -> 4
    # Unique right = A, B, C, E -> 4
    # Common       = A, B, C    -> 3
    #
    # 3 / 4 * 100 = 75%
    assert result == pytest.approx(75.0)


def test_likely_join_key():
    left = pd.DataFrame(
        {
            "sku_id": [
                "SKU001",
                "SKU002",
                "SKU003",
                "SKU004",
                "SKU005",
                "SKU006",
                "SKU007",
                "SKU008",
                "SKU009",
                "SKU010",
                "SKU011",
            ]
        }
    )

    right = pd.DataFrame(
        {
            "product_code": [
                "SKU001",
                "SKU002",
                "SKU003",
                "SKU004",
                "SKU005",
                "SKU006",
                "SKU007",
                "SKU008",
                "SKU009",
                "SKU010",
                "SKU011",
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert len(result) == 1

    relationship = result[0]

    assert relationship["left_column"] == "sku_id"
    assert relationship["right_column"] == "product_code"
    assert relationship["overlap_percentage"] == pytest.approx(
        100.0
    )
    assert relationship["classification"] == "likely_join_key"


def test_possible_relationship():
    left = pd.DataFrame(
        {
            "sku_id": [
                "SKU001",
                "SKU002",
                "SKU003",
                "SKU004",
                "SKU005",
                "SKU006",
                "SKU007",
                "SKU008",
                "SKU009",
                "SKU010",
                "SKU011",
            ]
        }
    )

    right = pd.DataFrame(
        {
            "product_code": [
                "SKU001",
                "SKU002",
                "SKU003",
                "SKU004",
                "SKU005",
                "SKU006",
                "SKU007",
                "SKU008",
                "SKU009",
                "SKU999",
                "SKU998",
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert len(result) == 1

    relationship = result[0]

    # 9 common / 11 smaller = 81.82%
    assert relationship["overlap_percentage"] == pytest.approx(
        81.82,
        abs=0.01,
    )
    assert relationship["classification"] == "possible"


def test_low_overlap_is_not_reported():
    left = pd.DataFrame(
        {
            "sku_id": [
                "SKU001",
                "SKU002",
                "SKU003",
                "SKU004",
                "SKU005",
                "SKU006",
                "SKU007",
                "SKU008",
                "SKU009",
                "SKU010",
                "SKU011",
            ]
        }
    )

    right = pd.DataFrame(
        {
            "product_code": [
                "PRODUCT001",
                "PRODUCT002",
                "PRODUCT003",
                "PRODUCT004",
                "PRODUCT005",
                "PRODUCT006",
                "PRODUCT007",
                "PRODUCT008",
                "PRODUCT009",
                "PRODUCT010",
                "SKU001",
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert result == []


def test_low_cardinality_columns_are_skipped():
    """
    Negative test requested by TL.

    warehouse_id has only 5 unique values.
    Therefore it must not be compared/reported.
    """

    left = pd.DataFrame(
        {
            "warehouse_id": [
                "WH1",
                "WH2",
                "WH3",
                "WH4",
                "WH5",
            ]
        }
    )

    right = pd.DataFrame(
        {
            "category": [
                "WH1",
                "WH2",
                "WH3",
                "WH4",
                "WH5",
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert result == []


def test_exactly_ten_unique_values_are_skipped():
    left = pd.DataFrame(
        {
            "id": [
                "ID001",
                "ID002",
                "ID003",
                "ID004",
                "ID005",
                "ID006",
                "ID007",
                "ID008",
                "ID009",
                "ID010",
            ]
        }
    )

    right = pd.DataFrame(
        {
            "id": [
                "ID001",
                "ID002",
                "ID003",
                "ID004",
                "ID005",
                "ID006",
                "ID007",
                "ID008",
                "ID009",
                "ID010",
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert result == []


def test_incompatible_types_are_skipped():
    left = pd.DataFrame(
        {
            "id": list(range(1, 12))
        }
    )

    right = pd.DataFrame(
        {
            "id": [
                str(value)
                for value in range(1, 12)
            ]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert result == []


def test_null_values_are_ignored():
    left = pd.Series(
        [
            "A",
            "B",
            "C",
            None,
            None,
        ]
    )

    right = pd.Series(
        [
            "A",
            "B",
            "C",
            "D",
            None,
        ]
    )

    result = calculate_overlap(
        left,
        right,
    )

    # Left unique = A, B, C -> 3
    # Right unique = A, B, C, D -> 4
    # Common = A, B, C -> 3
    #
    # 3 / 3 * 100 = 100%
    assert result == pytest.approx(100.0)


def test_invalid_dataframe():
    with pytest.raises(TypeError):
        discover_relationships(
            ["A", "B"],
            pd.DataFrame(
                {
                    "id": ["A", "B"]
                }
            ),
        )


def test_empty_columns_do_not_create_relationship():
    left = pd.DataFrame(
        {
            "id": [None, None, None]
        }
    )

    right = pd.DataFrame(
        {
            "id": [None, None, None]
        }
    )

    result = discover_relationships(
        left,
        right,
    )

    assert result == []