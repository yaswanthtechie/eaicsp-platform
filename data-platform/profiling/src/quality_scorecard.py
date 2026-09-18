from __future__ import annotations

from typing import Callable, Dict, Any

import numpy as np
import pandas as pd


def calculate_completeness(df: pd.DataFrame) -> float:
    """
    Calculate dataset completeness as the percentage of non-null values.

    Returns:
        float: Completeness score between 0 and 100.
    """
    if df.empty or df.size == 0:
        return 100.0

    total_values = df.size
    non_null_values = df.notna().sum().sum()

    return round((non_null_values / total_values) * 100, 2)


def calculate_validity(
    df: pd.DataFrame,
    rules: Dict[str, Callable[[pd.Series], pd.Series]] | None = None,
) -> float:
    """
    Calculate validity using configurable column-level rules.

    If no rules are provided, numeric columns are checked automatically
    for finite values.

    Each custom rule receives a pandas Series and must return
    a boolean Series.

    Example:
        {
            "quantity_sold": lambda s: s.ge(0),
            "unit_price": lambda s: s.ge(0),
        }

    Returns:
        float: Validity score between 0 and 100.
    """
    if df.empty:
        return 100.0

    # If no custom rules are provided, perform a generic
    # validity check on numeric columns.
    if not rules:
        rules = {
            column: lambda s: pd.Series(
                np.isfinite(s),
                index=s.index
            )
            for column in df.select_dtypes(include="number").columns
        }

    total_checked = 0
    total_valid = 0

    for column, rule in rules.items():
        if column not in df.columns:
            continue

        series = df[column].dropna()

        if series.empty:
            continue

        result = rule(series)

        if not isinstance(result, pd.Series):
            raise ValueError(
                f"Validity rule for '{column}' must return a pandas Series."
            )

        if len(result) != len(series):
            raise ValueError(
                f"Validity rule for '{column}' returned an incorrect number "
                "of results."
            )

        if not pd.api.types.is_bool_dtype(result):
            raise ValueError(
                f"Validity rule for '{column}' must return boolean values."
            )

        total_checked += len(result)
        total_valid += int(result.sum())

    if total_checked == 0:
        return 100.0

    return round((total_valid / total_checked) * 100, 2)


def calculate_consistency(
    df: pd.DataFrame,
    rules: list[Callable[[pd.DataFrame], pd.Series]] | None = None,
) -> float:
    """
    Calculate consistency using configurable dataframe-level rules.

    Each rule receives the complete DataFrame and must return
    a boolean Series indicating which rows pass the rule.

    Returns:
        float: Consistency score between 0 and 100.
    """
    if df.empty or not rules:
        return 100.0

    total_checked = 0
    total_passed = 0

    for rule in rules:
        result = rule(df)

        if not isinstance(result, pd.Series):
            raise ValueError(
                "Consistency rule must return a pandas Series."
            )

        if len(result) != len(df):
            raise ValueError(
                "Consistency rule returned an incorrect number of results."
            )

        if not pd.api.types.is_bool_dtype(result):
            raise ValueError(
                "Consistency rule must return boolean values."
            )

        total_checked += len(result)
        total_passed += int(result.sum())

    if total_checked == 0:
        return 100.0

    return round((total_passed / total_checked) * 100, 2)


def calculate_uniqueness(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> float:
    """
    Calculate uniqueness for selected key-like columns.

    If columns are not provided, uniqueness is not penalized because
    ordinary categorical columns are not expected to contain unique values.

    Returns:
        float: Uniqueness score between 0 and 100.
    """
    if df.empty or not columns:
        return 100.0

    scores = []

    for column in columns:
        if column not in df.columns:
            continue

        series = df[column].dropna()

        if series.empty:
            continue

        unique_ratio = series.nunique() / len(series)
        scores.append(unique_ratio * 100)

    if not scores:
        return 100.0

    return round(sum(scores) / len(scores), 2)


def generate_quality_scorecard(
    df: pd.DataFrame,
    *,
    version: int = 1,
    validity_rules: Dict[str, Callable[[pd.Series], pd.Series]] | None = None,
    consistency_rules: list[Callable[[pd.DataFrame], pd.Series]] | None = None,
    uniqueness_columns: list[str] | None = None,
) -> Dict[str, Any]:
    """
    Generate the complete Round 6 data quality scorecard.

    The overall score is the equal-weighted average of:
        - Completeness
        - Validity
        - Consistency
        - Uniqueness

    Returns:
        dict: Structured quality scorecard.
    """
    completeness = calculate_completeness(df)

    validity = calculate_validity(
        df,
        validity_rules,
    )

    consistency = calculate_consistency(
        df,
        consistency_rules,
    )

    uniqueness = calculate_uniqueness(
        df,
        uniqueness_columns,
    )

    overall_score = round(
        (
            completeness
            + validity
            + consistency
            + uniqueness
        ) / 4,
        2,
    )

    return {
        "version": version,
        "overall_score": overall_score,
        "components": {
            "completeness": completeness,
            "validity": validity,
            "consistency": consistency,
            "uniqueness": uniqueness,
        },
    }