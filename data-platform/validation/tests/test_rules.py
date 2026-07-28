import numpy as np
import pandas as pd

# Import all the rule functions from the business logic layer
from src.rules import (
    check_dates,
    check_strings,
    check_missing,
    check_negatives,
    check_outliers,
    check_duplicates
)


# ==========================================
# 1. Test Date Parsing Rule
# ==========================================
def test_check_dates():
    # Setup: 1 standard date, 1 bad date, 1 ambiguous European date
    df = pd.DataFrame({
        "date": ["2024-06-05", "invalid_date", "05/06/2024"]
    })

    # Test Detection: Should flag only the 2nd row (index 1)
    bad_mask = check_dates(df)
    assert bad_mask.tolist() == [False, True, False]

    # Test Cleaning:
    # 1. Should drop the unparseable date completely
    # 2. Should parse "05/06/2024" as June 5th (dayfirst=True), NOT May 6th.
    cleaned_df = check_dates.cleaner(df)

    assert len(cleaned_df) == 2
    assert 1 not in cleaned_df.index  # The invalid_date row was dropped

    # Anti-corruption assertion: verify dayfirst=True is working
    eu_date = cleaned_df.loc[2, "date"]
    assert eu_date.month == 6, f"Silent date corruption! Expected month 6, got {eu_date.month}"
    assert eu_date.day == 5


# ==========================================
# 2. Test String Standardization Rule
# ==========================================
def test_check_strings():
    # Setup: messy capitalization, trailing spaces, and hyphens
    df = pd.DataFrame({
        "product_name": [" IPHONE-15 ", "Galaxy S24"]
    })

    # Test Detection: This is a passive rule, it should flag NO rows (all False)
    bad_mask = check_strings(df)
    assert bad_mask.tolist() == [False, False]

    # Test Cleaning: Should lowercase, strip whitespace, and remove hyphens
    cleaned_df = check_strings.cleaner(df)

    # " IPHONE-15 " -> "iphone15"
    # "Galaxy S24"  -> "galaxy s24"
    assert cleaned_df["product_name"].tolist() == ["iphone 15", "galaxy s24"]


# ==========================================
# 3. Test Missing Quantity Rule
# ==========================================
def test_check_missing():
    # Setup: 1 good int, 1 missing, 1 zero
    df = pd.DataFrame({
        "quantity_sold": [5.0, np.nan, 0.0]
    })

    # Test Detection: Should flag only the NaN row
    bad_mask = check_missing(df)
    assert bad_mask.tolist() == [False, True, False]

    # Test Cleaning: Should completely drop the NaN row
    cleaned_df = check_missing.cleaner(df)

    assert len(cleaned_df) == 2
    assert cleaned_df["quantity_sold"].tolist() == [5.0, 0.0]


# ==========================================
# 4. Test Negative Quantity Rule
# ==========================================
def test_check_negatives():
    # Setup: 1 positive, 1 negative, 1 zero
    df = pd.DataFrame({
        "quantity_sold": [5.0, -2.0, 0.0]
    })

    # Test Detection: Should flag only the negative row
    bad_mask = check_negatives(df)
    assert bad_mask.tolist() == [False, True, False]

    # Test Cleaning: Should NOT delete, but should add a boolean flag column
    cleaned_df = check_negatives.cleaner(df)

    assert len(cleaned_df) == 3  # No rows were deleted
    assert "flagged_for_review" in cleaned_df.columns
    assert cleaned_df["flagged_for_review"].tolist() == [False, True, False]

    # Test Re-validation: Ensure it ignores rows that are ALREADY flagged
    post_mask = check_negatives(cleaned_df)
    assert post_mask.tolist() == [False, False, False]


# ==========================================
# 5. Test Outlier Quantity Rule
# ==========================================
# def test_check_outliers():
#     # Setup: 20 normal values, and 1 massive outlier
#     # We need enough baseline data so the outlier doesn't skew the std dev too much!
#     normal_values = [10] * 20
#     df = pd.DataFrame({
#         "quantity_sold": normal_values + [1000]
#     })
#
#     # Test Detection: > 3 standard deviations from the mean
#     bad_mask = check_outliers(df)
#
#     # Only the last row (the 1000) should be flagged
#     expected = [False] * 20 + [True]
#     assert bad_mask.tolist() == expected
# ==========================================
# 5. Test Outlier Quantity Rule
# ==========================================
def test_check_outliers():
    # Setup: A normal spread of sales data, plus one massive outlier
    # Normal range: 8 to 12.
    df = pd.DataFrame({
        "quantity_sold": [10, 9, 11, 12, 8, 10, 9, 11, 10, 1000]
    })

    # Test Detection: Values outside 1.5 * IQR
    bad_mask = check_outliers(df)

    # Only the final row (1000) should be flagged
    expected = [False] * 9 + [True]
    assert bad_mask.tolist() == expected


# ==========================================
# 6. Test Duplicate Rows Rule
# ==========================================
def test_check_duplicates():
    # Setup: Row 0 and Row 1 are exact copies. Row 2 is unique.
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        "product_name": ["iPhone", "iPhone", "Galaxy"],
        "quantity_sold": [5.0, 5.0, 3.0]
    })

    # Test Detection: Should keep the first (0), flag the second (1)
    bad_mask = check_duplicates(df)
    assert bad_mask.tolist() == [False, True, False]

    # Test Cleaning: Should drop the flagged duplicate row
    cleaned_df = check_duplicates.cleaner(df)

    assert len(cleaned_df) == 2
    assert cleaned_df.index.tolist() == [0, 2]
