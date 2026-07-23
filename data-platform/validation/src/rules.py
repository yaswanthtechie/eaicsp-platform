import pandas as pd

from src.validator import rule


# --- Cleaners ---

def parse_dates(df):
    df_c = df.copy()
    df_c['date'] = pd.to_datetime(df_c['date'], errors='coerce', format='mixed')
    return df_c

def standardize_products(df):
    df_c = df.copy()
    df_c['product_name'] = (
        df_c['product_name']
        .astype(str)
        .str.lower()
        .str.strip()
        .str.replace('-', '', regex=False)
    )
    return df_c

def drop_missing_or_invalid_dates(df):
    # Drop both missing quantities AND rows where date turned into NaT
    return df.dropna(subset=['quantity_sold', 'date'])

def flag_negatives(df):
    df_c = df.copy()
    if 'flagged_for_review' not in df_c.columns:
        df_c['flagged_for_review'] = False
    df_c.loc[df_c['quantity_sold'] < 0, 'flagged_for_review'] = True
    return df_c


# Standardize formats first
@rule(name="unparseable_dates", severity="error", cleaner=parse_dates)
def check_dates(df):
    return pd.to_datetime(df['date'], errors='coerce', format='mixed').isna()

@rule(name="standardize_strings", severity="info", cleaner=standardize_products)
def check_strings(df):
    # Passive rule: cleans strings so downstream rules see standard text
    return pd.Series(False, index=df.index)

@rule(name="missing_quantity", severity="error", cleaner=lambda df: df.dropna(subset=['quantity_sold']))
def check_missing(df):
    return df['quantity_sold'].isna()

@rule(name="negative_quantity", severity="warning", cleaner=flag_negatives)
def check_negatives(df):
    return df['quantity_sold'] < 0


# Runs AFTER dates and strings are standardized!
@rule(name="duplicate_rows", severity="error",
      cleaner=lambda df: df.drop_duplicates())
def check_duplicates(df):
    return df.duplicated(keep='first')

