import pandas as pd
import pytest
import numpy as np

from rules.custom_rules import (
    check_unparseable_dates,
    check_outliers,
    check_negatives,
    check_duplicate_rows,
    standardize_products,
    flag_negatives,
    standardize_dates,
    drop_duplicate_rows,
    check_composite_unique,
    check_composite_unique_stream,
    clean_whitespace_and_case  # Newly added rule
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
            '02/01/2026',  # 1: Ambiguous (Feb 1 or Jan 2?) - must be preserved and flagged
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
    # Apply the transform first to mirror the pipeline's df_working behavior
    df_working = standardize_dates(sample_df, field='order_date')

    result = check_unparseable_dates(df_working, field='order_date')

    # Row 1 is '02/01/2026' (ambiguous, so preserved and flagged).
    # Row 2 is 'NOT_A_DATE'
    expected = [False, True, True, False, False]
    assert list(result) == expected


def test_check_outliers(sample_df):
    """Test that values outside the 1.5 * IQR bounds are flagged as True."""
    result = check_outliers(sample_df, field='quantity_sold')
    expected = [False, True, True, False, False]
    assert list(result) == expected


def test_check_negatives(sample_df):
    """Test that numbers less than zero are flagged as True."""
    result = check_negatives(sample_df, field='quantity_sold')
    expected = [False, True, False, False, False]
    assert list(result) == expected


def test_check_duplicate_rows(sample_df):
    """Test that entirely duplicated rows are flagged."""
    result = check_duplicate_rows(sample_df)
    expected = [False, False, False, False, True]
    assert list(result) == expected


def test_check_composite_unique():
    """Test that duplicated rows based on a subset of columns are flagged."""
    df = pd.DataFrame({
        'A': [1, 1, 2, 3],
        'B': [1, 1, 2, 4],
        'C': ['x', 'y', 'z', 'w']
    })
    result = check_composite_unique(df, subset=['A', 'B'], keep=False)
    assert list(result) == [True, True, False, False]


def test_check_composite_unique_stream():
    """Test both branches of the streaming bypass function."""
    df_stream = pd.DataFrame({'_global_dup_mask': [True, False, True]})
    result_stream = check_composite_unique_stream(df_stream)
    assert list(result_stream) == [True, False, True]

    df_fallback = pd.DataFrame({'A': [1, 2, 3]})
    result_fallback = check_composite_unique_stream(df_fallback)
    assert list(result_fallback) == [False, False, False]


# ==========================================
# TRANSFORMATION TESTS
# ==========================================

def test_standardize_products(sample_df):
    """Test string lowercasing, stripping, and character replacement."""
    clean_df = standardize_products(sample_df, field='product_name', target_char='-', replace_char=' ')
    products = clean_df['product_name'].tolist()
    assert products[0] == 'iphone 15'
    assert products[1] == 'galaxy s24'
    assert products[2] == 'pixel pro'
    assert products[4] == 'iphone 15'


def test_flag_negatives(sample_df):
    """Test that a new boolean column is added and correctly flags negatives."""
    clean_df = flag_negatives(sample_df, field='quantity_sold')
    assert 'flagged_for_review' in clean_df.columns
    expected = [False, True, False, False, False]
    assert list(clean_df['flagged_for_review']) == expected


def test_standardize_dates(sample_df):
    """Test that strict date formats are unified and ambiguous formats are safely preserved."""
    clean_df = standardize_dates(sample_df, field='order_date')
    dates = clean_df['order_date']

    assert dates[0] == '2026-07-31'  # Kept valid ISO
    assert dates[1] == '02/01/2026'  # Ambiguous: preserved, never guessed
    assert dates[2] == 'NOT_A_DATE'  # Preserved invalid string for validation
    assert pd.isna(dates[3])  # Handled Nulls properly


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" 2024-03-18 ", "2024-03-18"),  # only whitespace needed fixing
        ("Mar 18 2024", "2024-03-18"),   # month written as a word
        ("March 18 2024", "2024-03-18"),
        ("24/03/2024", "2024-03-24"),    # 24 can't be a month -> day first
        ("03/24/2024", "2024-03-24"),    # 24 can't be a month -> month first
        ("05/05/2024", "2024-05-05"),    # same date either way
        ("02/01/2024", "02/01/2024"),    # ambiguous -> left for unparseable_dates
        ("31/02/2024", "31/02/2024"),    # not a real date -> left for unparseable_dates
        ("NOT_A_DATE", "NOT_A_DATE"),
        (pd.Timestamp("2024-03-18"), "2024-03-18"),  # already a real date object
    ],
)
def test_standardize_dates_only_fixes_unambiguous_dates(raw, expected):
    out = standardize_dates(pd.DataFrame({"d": [raw]}), field="d")["d"].iloc[0]
    assert out == expected


def test_standardize_dates_keeps_nulls_as_nulls():
    out = standardize_dates(pd.DataFrame({"d": [None, float("nan"), "  "]}), field="d")["d"]
    assert out.isna().all()


def test_drop_duplicate_rows(sample_df):
    """Test that perfectly identical rows are dropped."""
    clean_df = drop_duplicate_rows(sample_df)
    assert len(clean_df) == 4
    assert list(clean_df.index) == [0, 1, 2, 3]


def test_clean_whitespace_and_case():
    """Test safe trimming of whitespace and casing standardization."""
    df = pd.DataFrame({'sku': ['  sku-123  ', 'SKU-456', None]})

    # Test Uppercase
    df_upper = clean_whitespace_and_case(df, field='sku', target_case='upper')
    assert df_upper['sku'].iloc[0] == 'SKU-123'
    assert df_upper['sku'].iloc[1] == 'SKU-456'
    assert pd.isna(df_upper['sku'].iloc[2])  # Properly checks for NaN/None

    # Test Lowercase
    df_lower = clean_whitespace_and_case(df, field='sku', target_case='lower')
    assert df_lower['sku'].iloc[0] == 'sku-123'
    assert df_lower['sku'].iloc[1] == 'sku-456'
    assert pd.isna(df_lower['sku'].iloc[2])  # Properly checks for NaN/None