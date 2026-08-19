import logging

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_SCHEMA = {
    "date": {
        "category": "datetime",
        "required": True
    },
    "sku_id": {
        "category": "string",
        "required": True
    },
    "warehouse_id": {
        "category": "string",
        "required": True
    },
    "quantity_sold": {
        "category": "integer",
        "required": True
    },
    "unit_price": {
        # NUMERIC(12,2) in the DDL covers both whole-number prices (e.g. 773,
        # which pandas infers as int64) and genuinely fractional prices (e.g.
        # 19.99, inferred as float64), so both dtypes are valid here.
        "category": "numeric",
        "required": True
    },
}

# Checked by dtype *category* rather than an exact dtype string (e.g.
# "datetime64[us]" vs "datetime64[ns]") so this doesn't break across pandas
# versions/resolutions or reject valid numeric variants.
_CATEGORY_CHECKS = {
    "datetime": pd.api.types.is_datetime64_any_dtype,
    "string": lambda s: pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s),
    "integer": pd.api.types.is_integer_dtype,
    "numeric": pd.api.types.is_numeric_dtype,
}


def validate_schema_against(df, schema):
    """Generic schema check, driven by an arbitrary {column: {category, required}}
    dict (e.g. loaded from pipeline_config.yaml). validate_schema() below is
    just this function called with the sales-specific EXPECTED_SCHEMA."""

    for column, rule in schema.items():

        if rule["required"] and column not in df.columns:

            logger.error(f"Missing required column : {column}")

            raise ValueError(
                f"Missing required column : {column}"
            )



    for column, rule in schema.items():

        if column not in df.columns:
            continue

        category = rule["category"]
        check = _CATEGORY_CHECKS[category]

        if not check(df[column]):

            actual = str(df[column].dtype)

            logger.error(
                f"{column} datatype mismatch. "
                f"Expected category={category} "
                f"Actual dtype={actual}"
            )

            raise TypeError(
                f"{column} datatype mismatch"
            )



    for column in df.columns:

        if column not in schema:

            logger.warning(
                f"Unexpected column detected : {column}"
            )

    logger.info("Schema validation passed")

    return True


def validate_schema(df):
    return validate_schema_against(df, EXPECTED_SCHEMA)