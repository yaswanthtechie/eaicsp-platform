import re
from datetime import datetime
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

_MONTH_NAME_FORMATS = ("%b %d %Y", "%B %d %Y")
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")

def _normalize_one_date(value):
    """Return an ISO 'YYYY-MM-DD' string when the date can only mean ONE thing.

    Returns None for nulls. Returns the (stripped) original string when the
    date is ambiguous or invalid, so the unparseable_dates rule flags it.

    Unambiguous:  2024-03-18, Mar 18 2024, 24/03/2024 (24 can't be a month),
                  03/24/2024 (24 can't be a month), 05/05/2024 (same either way)
    Ambiguous:    02/01/2024 (Feb 1 or Jan 2?)  -> left as-is and flagged
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    if text == "":
        return None

    # 1. Already ISO.
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass

    # 2. Month written as a word - no day/month confusion possible.
    for fmt in _MONTH_NAME_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 3. Numeric A/B/YYYY - only safe when exactly one reading is possible.
    match = _NUMERIC_DATE.match(text)
    if match:
        a, b, year = (int(part) for part in match.groups())
        if a == b:
            day, month = a, b          # 05/05/2024: same date either way
        elif a > 12 >= b:
            day, month = a, b          # 24/03/2024: a must be the day
        elif b > 12 >= a:
            day, month = b, a          # 03/24/2024: b must be the day
        else:
            return text                # 02/01/2024: genuinely ambiguous -> flag, never guess
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return text                # e.g. 31/02/2024: not a real date -> flag

    # 4. Anything else (e.g. 'NOT_A_DATE') is left for unparseable_dates to flag.
    return text


@register_rule()
def standardize_dates(df: pd.DataFrame, *, field: str = 'order_date', **kwargs) -> pd.DataFrame:
    """Converts dates to YYYY-MM-DD only when they can mean exactly one date.
    Ambiguous dates (like 02/01/2024) and invalid strings are left unchanged
    so the unparseable_dates rule flags them for a human."""
    df_c = df.copy()
    if field in df_c.columns:
        df_c[field] = df_c[field].map(_normalize_one_date).astype(object)
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
    """Trims leading/trailing spaces and converts the text to one consistent case (upper or lower)."""
    if target_case not in ('upper', 'lower'):
        raise ValueError(f"target_case must be 'upper' or 'lower', got '{target_case}'")
    df_c = df.copy()
    if field in df_c.columns:
        mask = df_c[field].notna()
        cleaned = df_c.loc[mask, field].astype(str).str.strip()
        df_c.loc[mask, field] = cleaned.str.upper() if target_case == 'upper' else cleaned.str.lower()
    return df_c