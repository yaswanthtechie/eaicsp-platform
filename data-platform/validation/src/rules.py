import pandas as pd
from src.validator import Rule


# --- Cleaners ---

def parse_dates(df):
    df_c = df.copy()

    # 1. Try strict ISO parsing first to protect YYYY-MM-DD from being flipped
    iso_dates = pd.to_datetime(df_c['date'], format='%Y-%m-%d', errors='coerce')

    # 2. Parse the remaining messy/European dates with dayfirst=True
    mixed_dates = pd.to_datetime(df_c['date'], format='mixed', dayfirst=True, errors='coerce')

    # 3. Combine them: use ISO if it worked, otherwise fall back to the mixed parser
    df_c['date'] = iso_dates.fillna(mixed_dates)

    # Drop rows where the date is still NaT
    return df_c.dropna(subset=['date'])

def standardize_products(df):
    df_c = df.copy()
    df_c['product_name'] = (
        df_c['product_name']
        .astype(str)
        .str.lower()
        .str.strip()
        .str.replace('-', ' ', regex=False)
    )
    return df_c

def flag_negatives(df):
    df_c = df.copy()
    if 'flagged_for_review' not in df_c.columns:
        df_c['flagged_for_review'] = False
    df_c.loc[df_c['quantity_sold'] < 0, 'flagged_for_review'] = True
    return df_c

# --- Rules ---

# Standardize formats first
@Rule(name="unparseable_dates", severity="error", cleaner=parse_dates, priority=10)
def check_dates(df):
    # Use the same two-pass logic to detect failures without corrupting the check
    iso_dates = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
    mixed_dates = pd.to_datetime(df['date'], format='mixed', dayfirst=True, errors='coerce')

    combined_dates = iso_dates.fillna(mixed_dates)
    return combined_dates.isna()

@Rule(name="standardize_strings", severity="info", cleaner=standardize_products, priority=10)
def check_strings(df):
    # Passive rule: cleans strings so downstream rules see standard text
    return pd.Series(False, index=df.index)

@Rule(name="missing_quantity", severity="error", cleaner=lambda df: df.dropna(subset=['quantity_sold']), priority=50)
def check_missing(df):
    return df['quantity_sold'].isna()

@Rule(name="negative_quantity", severity="warning", cleaner=flag_negatives)
def check_negatives(df):
    mask = df['quantity_sold'] < 0
    # Ignore rows that have already been flagged if checking post-clean
    if 'flagged_for_review' in df.columns:
        mask = mask & (~df['flagged_for_review'])
    return mask

# Runs AFTER dates and strings are standardized!
# Runs late (Priority 90) - waits for standardizers!
@Rule(name="duplicate_rows", severity="error", cleaner=lambda df: df.drop_duplicates(), priority=90)
def check_duplicates(df):
    return df.duplicated(keep='first')

# outliers detection using robust IQR method)
@Rule(name="outlier_quantity", severity="warning", priority=50)
def check_outliers(df):
    # Calculate 25th (Q1) and 75th (Q3) percentiles
    Q1 = df['quantity_sold'].quantile(0.25)
    Q3 = df['quantity_sold'].quantile(0.75)

    # Calculate Interquartile Range
    IQR = Q3 - Q1

    # Define bounds
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    # Flag anything outside the bounds.
    # (Pandas safely evaluates NaNs as False in these comparisons)
    return (df['quantity_sold'] < lower_bound) | (df['quantity_sold'] > upper_bound)

