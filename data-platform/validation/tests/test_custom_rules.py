import pandas as pd
import pytest
import numpy as np

# Adjust the import path if your file is located elsewhere!
from src.custom_rules import (
    check_unparseable_dates,
    check_outliers,
    check_negatives,
    check_duplicate_rows,
    standardize_products,
    flag_negatives,
    standardize_dates,
    drop_duplicate_rows
)


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def sample_df():
    """
    Creates a standardized DataFrame designed to trigger
    every condition in our custom validation and transformation rules.
    """
    data = {
        'order_date': [
            '2026-07-31',  # 0: Valid ISO date
            '15/08/2026',  # 1: Valid mixed date (dayfirst)
            'NOT_A_DATE',  # 2: Invalid string (Unparseable)
            None,  # 3: Null value
            '2026-07-31'  # 4: Exact duplicate of Row 0
        ],
        'quantity_sold': [
            10,  # 0: Valid/Normal
            -5,  # 1: Negative
            1000,  # 2: Extreme High Outlier
            15,  # 3: Valid/Normal
            10  # 4: Exact duplicate of Row 0
        ],
        'product_name': [
            ' iPhone 15 ',  # 0: Needs strip and lowercase
            'GALAXY-S24',  # 1: Needs target_char replacement and lowercase
            'pixel pro',  # 2: Already perfect
            None,  # 3: Null handling
            ' iPhone 15 '  # 4: Exact duplicate of Row 0
        ]
    }
    return pd.DataFrame(data)


# ==========================================
# VALIDATION TESTS
# ==========================================

def test_check_unparseable_dates(sample_df):
    """Test that only non-null, unparseable strings are flagged as True."""
    result = check_unparseable_dates(sample_df, field='order_date')

    # Row 2 is 'NOT_A_DATE', everything else is parsable or intentionally null
    expected = [False, False, True, False, False]
    assert list(result) == expected


def test_check_outliers(sample_df):
    """Test that values outside the 1.5 * IQR bounds are flagged as True."""
    result = check_outliers(sample_df, field='quantity_sold')

    # In [10, -5, 1000, 15, 10]:
    # Q1 = 10, Q3 = 15, IQR = 5. Lower Bound = 2.5, Upper Bound = 22.5
    # Row 1 (-5) and Row 2 (1000) are outside the bounds
    expected = [False, True, True, False, False]
    assert list(result) == expected


def test_check_negatives(sample_df):
    """Test that numbers less than zero are flagged as True."""
    result = check_negatives(sample_df, field='quantity_sold')

    # Only Row 1 is negative (-5)
    expected = [False, True, False, False, False]
    assert list(result) == expected


def test_check_duplicate_rows(sample_df):
    """Test that entirely duplicated rows are flagged."""
    result = check_duplicate_rows(sample_df)

    # Row 4 is a perfect copy of Row 0. Using keep='first', Row 4 is True.
    expected = [False, False, False, False, True]
    assert list(result) == expected


# ==========================================
# TRANSFORMATION TESTS
# ==========================================

def test_standardize_products(sample_df):
    """Test string lowercasing, stripping, and character replacement."""
    clean_df = standardize_products(sample_df, field='product_name', target_char='-', replace_char=' ')

    products = clean_df['product_name'].tolist()
    assert products[0] == 'iphone 15'  # Stripped and lowercased
    assert products[1] == 'galaxy s24'  # Hyphen replaced and lowercased
    assert products[2] == 'pixel pro'  # Untouched
    assert products[4] == 'iphone 15'  # Stripped and lowercased


def test_flag_negatives(sample_df):
    """Test that a new boolean column is added and correctly flags negatives."""
    clean_df = flag_negatives(sample_df, field='quantity_sold')

    assert 'flagged_for_review' in clean_df.columns
    # Only Row 1 should be flagged True
    expected = [False, True, False, False, False]
    assert list(clean_df['flagged_for_review']) == expected


def test_standardize_dates(sample_df):
    """Test that various date formats unify to YYYY-MM-DD strings."""
    clean_df = standardize_dates(sample_df, field='order_date')

    dates = clean_df['order_date']
    assert dates[0] == '2026-07-31'  # Kept valid ISO
    assert dates[1] == '2026-08-15'  # Parsed mixed/dayfirst properly
    assert pd.isna(dates[2])  # Handled invalid string (NaT)
    assert pd.isna(dates[3])  # Handled Nulls properly


def test_drop_duplicate_rows(sample_df):
    """Test that perfectly identical rows are dropped."""
    clean_df = drop_duplicate_rows(sample_df)

    # Original length was 5, Row 4 was a duplicate
    assert len(clean_df) == 4
    # Ensure Row 4 is completely gone from the index
    assert list(clean_df.index) == [0, 1, 2, 3]