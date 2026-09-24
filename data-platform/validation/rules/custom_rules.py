import pandas as pd
from typing import Optional, Literal
from src.registry import register_rule

# ==========================================
# VALIDATION RULES (type: custom)
# ==========================================

@register_rule()
def check_unparseable_dates(df: pd.DataFrame, *, field: str, **kwargs) -> pd.Series:
    """Flags dates that failed standard parsing and remained as malformed strings."""
    valid_format = df[field].astype(str).str.match(r'^\d{4}-\d{2}-\d{2}$')
    return ~valid_format & df[field].notna()

@register_rule()
def check_outliers(
    df: pd.DataFrame,
    *,
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

@register_rule()
def check_negatives(df: pd.DataFrame, *, field: str, **kwargs) -> pd.Series:
    """Returns a boolean mask for rows where the quantity is less than zero."""
    return df[field] < 0

@register_rule()
def check_duplicate_rows(
    df: pd.DataFrame,
    *,
    field: Optional[str] = None,
    keep: Literal['first', 'last', False] = 'first',
    **kwargs
) -> pd.Series:
    """Checks if an entire row is an exact duplicate of another row."""
    return df.duplicated(keep=keep)

@register_rule()
def check_composite_unique(
    df: pd.DataFrame,
    *,
    subset: list,
    keep: Literal['first', 'last', False] = False,
    **kwargs
) -> pd.Series:
    """Checks for duplicated rows based on a subset of columns (Composite Key)."""
    return df.duplicated(subset=subset, keep=keep)


# ==========================================
# TRANSFORMATION RULES (type: transform)
# ==========================================

@register_rule()
def standardize_products(
    df: pd.DataFrame,
    *,
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

@register_rule()
def flag_negatives(df: pd.DataFrame, *, field: str = 'quantity_sold', **kwargs) -> pd.DataFrame:
    """Adds a 'flagged_for_review' column for rows with negative quantities."""
    df_c = df.copy()
    if 'flagged_for_review' not in df_c.columns:
        df_c['flagged_for_review'] = False
    if field in df_c.columns:
        df_c.loc[df_c[field] < 0, 'flagged_for_review'] = True
    return df_c


@register_rule()
def standardize_dates(df: pd.DataFrame, *, field: str = 'order_date', **kwargs) -> pd.DataFrame:
    """Safely unifies strict date strings. Preserves ambiguous or invalid strings for validation."""
    df_c = df.copy()
    if field in df_c.columns:
        # 1. Safely strip whitespace (this is a deterministic, safe fix)
        cleaned_strings = df_c[field].astype(str).str.strip()

        # 2. Strict parsing only. Do not guess day/month order.
        iso_dates = pd.to_datetime(cleaned_strings, format='%Y-%m-%d', errors='coerce')

        # 3. If it fails strict parsing, keep the cleaned string so the unparseable_dates rule catches it
        df_c[field] = iso_dates.dt.strftime('%Y-%m-%d').fillna(cleaned_strings)

        # 4. Restore proper nulls
        null_mask = df_c[field].isin(['nan', 'None', ''])
        df_c.loc[null_mask, field] = None

    return df_c

@register_rule()
def drop_duplicate_rows(
    df: pd.DataFrame,
    *,
    keep: Literal['first', 'last', False] = 'first',
    **kwargs
) -> pd.DataFrame:
    """Drops entirely duplicated rows from the dataset."""
    return df.drop_duplicates(keep=keep)

@register_rule()
def check_composite_unique_stream(df: pd.DataFrame, **kwargs) -> pd.Series:
    """Bypass function for streaming validation."""
    if '_global_dup_mask' in df.columns:
        return df['_global_dup_mask']
    return pd.Series([False] * len(df), index=df.index)

@register_rule()
def clean_whitespace_and_case(df: pd.DataFrame, *, field: str, target_case: str = 'upper', **kwargs) -> pd.DataFrame:
    """Safely trims whitespace and standardizes case for string columns."""
    df_c = df.copy()
    if field in df_c.columns:
        mask = df_c[field].notna()
        if target_case == 'upper':
            df_c.loc[mask, field] = df_c.loc[mask, field].astype(str).str.strip().str.upper()
        else:
            df_c.loc[mask, field] = df_c.loc[mask, field].astype(str).str.strip().str.lower()
    return df_c