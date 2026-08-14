import pandas as pd
import numpy as np

from src.validator import DataValidator
from src.rules import (
    check_dates,
    check_strings,
    check_missing,
    check_negatives,
    check_duplicates
)


def test_pipeline_end_to_end():
    """
    Tests the complete pipeline lifecycle:
    - Sorts shuffled rules by priority.
    - Validates messy data accurately.
    - Applies standardizers first to unmask hidden duplicates.
    - Checks for silent date corruption (dayfirst=True).
    - Ensures clean final validation.
    """

    # 1. SETUP: Create synthetic "messy" data hitting every rule in 5 rows
    raw_data = pd.DataFrame({
        # Row 0 & 1: Hidden duplicates.
        # -> Row 0 tests dayfirst=True ("05/06/2024" should parse as June 5th, not May 6th).
        # -> Row 1 uses standard ISO format but messy string casing/hyphens.
        # Row 2: Unparseable date (should drop).
        # Row 3: Missing quantity (should drop).
        # Row 4: Negative quantity (should flag, but not drop).
        "date": ["05/06/2024", "2024-06-05", "invalid_date", "2024-06-07", "2024-06-08"],
        "product_name": ["iphone 15 ", "IPHONE-15", "Galaxy S24", "Pixel 8", "MacBook"],
        "quantity_sold": [5.0, 5.0, 10.0, np.nan, -2.0]
    })


    # 2. EXECUTION: Pass the rules completely out of order
    shuffled_rules = [check_duplicates, check_missing, check_dates, check_strings, check_negatives]
    dv = DataValidator(rules=shuffled_rules)

    # Validate -> Clean -> Re-validate
    initial_report = dv.validate(raw_data)
    clean_df = dv.clean(raw_data)
    clean_report = dv.validate(clean_df)

    # 3. ASSERTIONS: Architecture & Priority Sorting
    # Verify the validator actually sorted the rules under the hood
    rule_names_in_order = [r.rule_name for r in dv.rules]
    # Priority 10 rules (dates, strings) should be first
    assert rule_names_in_order[0] in ["unparseable_dates", "standardize_strings"]
    # Priority 90 rule (duplicates) MUST be last to catch unmasked duplicates
    assert rule_names_in_order[-1] == "duplicate_rows"

    # 4. ASSERTIONS: Initial Validation
    assert initial_report["is_clean"] is False
    assert initial_report["issues"]["unparseable_dates"]["count"] == 1
    assert initial_report["issues"]["missing_quantity"]["count"] == 1
    # Note: Initial report might not see the duplicate yet because the strings/dates aren't cleaned.

    # 5. ASSERTIONS: Cleaning Logic & Anti-Corruption
    # 5 original rows - 1 bad date - 1 missing qty - 1 duplicate = 2 rows remaining
    assert len(clean_df) == 2

    # Date Anti-Corruption: Row 0 ("05/06/2024") must resolve to June 5th, not May 6th
    parsed_date = clean_df.iloc[0]["date"]
    assert parsed_date.month == 6, f"Silent date corruption! Expected month 6, got {parsed_date.month}"
    assert parsed_date.day == 5

    # String Standardization: Ensure the trailing space and hyphens were resolved
    assert clean_df.iloc[0]["product_name"] == "iphone 15"

    # Business Logic: Ensure the negative row survived but was flagged
    assert clean_df["flagged_for_review"].sum() == 1
    assert clean_df.iloc[1]["quantity_sold"] == -2.0

    # 6. ASSERTIONS: Post-Cleaning Validation
    # The final report should be 100% clean (negatives are flagged, bad dates dropped)
    assert clean_report["is_clean"] is True
    assert "unparseable_dates" not in clean_report["issues"]
    assert "duplicate_rows" not in clean_report["issues"]
    assert "missing_quantity" not in clean_report["issues"]