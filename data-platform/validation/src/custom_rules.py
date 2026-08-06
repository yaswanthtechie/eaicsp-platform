import pandas as pd
from typing import Optional, Literal


# ==========================================
# VALIDATION RULES (type: custom)
# Uses 'field' because validator.py explicitly passes it
# ==========================================

def check_unparseable_dates(
    df: pd.DataFrame,
    field: str,
    iso_format: str = '%Y-%m-%d',
    mixed_format: str = 'mixed',
    **kwargs
) -> pd.Series:
    """Checks for dates that cannot be parsed using provided formats."""
    iso_dates = pd.to_datetime(df[field], format=iso_format, errors='coerce')
    mixed_dates = pd.to_datetime(df[field], format=mixed_format, dayfirst=True, errors='coerce')
    combined_dates = iso_dates.fillna(mixed_dates)

    return combined_dates.isna() & df[field].notna()


def check_outliers(
    df: pd.DataFrame,
    field: str,
    lower_q: float = 0.25,
    upper_q: float = 0.75,
    multiplier: float = 1.5,
    **kwargs
) -> pd.Series:
    """Calculates IQR and returns True for rows outside the bounds."""
    Q1 = df[field].quantile(lower_q)
    Q3 = df[field].quantile(upper_q)
    IQR = Q3 - Q1

    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR

    return (df[field] < lower_bound) | (df[field] > upper_bound)


def check_negatives(df: pd.DataFrame, field: str, **kwargs) -> pd.Series:
    """Returns a boolean mask for rows where the quantity is less than zero."""
    return df[field] < 0


def check_duplicate_rows(
    df: pd.DataFrame,
    field: Optional[str] = None,
    keep: Literal['first', 'last', False] = 'first',
    **kwargs
) -> pd.Series:
    """Checks if an entire row is an exact duplicate of another row."""
    return df.duplicated(keep=keep)


def check_composite_unique(
    df: pd.DataFrame,
    subset: list,
    keep: Literal['first', 'last', False] = False,
    **kwargs
) -> pd.Series:
    """Checks for duplicated rows based on a subset of columns (Composite Key)."""
    return df.duplicated(subset=subset, keep=keep)


# ==========================================
# TRANSFORMATION RULES (type: transform)
# Uses 'target_col' to bypass the standard keys filter
# ==========================================

def standardize_products(
    df: pd.DataFrame,
    field: str = 'product_name',
    target_char: str = '-',
    replace_char: str = ' ',
    **kwargs
) -> pd.DataFrame:
    """Cleans text columns by forcing lowercase, stripping whitespace, and replacing characters."""
    df_c = df.copy()

    if field in df_c.columns:
        df_c[field] = (
            df_c[field]
            .astype(str)
            .str.lower()
            .str.strip()
            .str.replace(target_char, replace_char, regex=False)
        )
    return df_c


def flag_negatives(df: pd.DataFrame, field: str = 'quantity_sold', **kwargs) -> pd.DataFrame:
    """Adds a 'flagged_for_review' column for rows with negative quantities."""
    df_c = df.copy()
    if 'flagged_for_review' not in df_c.columns:
        df_c['flagged_for_review'] = False

    if field in df_c.columns:
        df_c.loc[df_c[field] < 0, 'flagged_for_review'] = True

    return df_c


def standardize_dates(df: pd.DataFrame, field: str = 'order_date', **kwargs) -> pd.DataFrame:
    """Unifies various date string formats into a standard YYYY-MM-DD format."""
    df_c = df.copy()
    if field in df_c.columns:
        # Try strict ISO parsing first
        iso_dates = pd.to_datetime(df_c[field], format='%Y-%m-%d', errors='coerce')
        # Parse remaining messy dates
        mixed_dates = pd.to_datetime(df_c[field], format='mixed', dayfirst=True, errors='coerce')

        # Combine and format to string
        df_c[field] = iso_dates.fillna(mixed_dates).dt.strftime('%Y-%m-%d')
    return df_c


def drop_duplicate_rows(
    df: pd.DataFrame,
    keep: Literal['first', 'last', False] = 'first',
    **kwargs
) -> pd.DataFrame:
    """Drops entirely duplicated rows from the dataset."""
    return df.drop_duplicates(keep=keep)