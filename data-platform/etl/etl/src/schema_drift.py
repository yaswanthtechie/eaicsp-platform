EXPECTED_SCHEMA = {
    "date": "datetime64[ns]",
    "sku_id": "object",
    "warehouse_id": "object",
    "quantity_sold": "int64",
    "unit_price": "int64",
}


def detect_schema_drift(df):

    expected_cols = set(EXPECTED_SCHEMA.keys())
    actual_cols = set(df.columns)

    added_columns = sorted(actual_cols - expected_cols)
    removed_columns = sorted(expected_cols - actual_cols)

    datatype_changes = {}

    for column in expected_cols.intersection(actual_cols):

        expected_dtype = EXPECTED_SCHEMA[column]
        actual_dtype = str(df[column].dtype)

        
        if (
            expected_dtype in ["object", "str"]
            and actual_dtype in ["object", "str"]
        ):
            continue

        
        if (
            expected_dtype.startswith("datetime64")
            and actual_dtype.startswith("datetime64")
        ):
            continue

        if expected_dtype != actual_dtype:

            datatype_changes[column] = {
                "expected": expected_dtype,
                "actual": actual_dtype,
            }

    return {
        "added_columns": added_columns,
        "removed_columns": removed_columns,
        "datatype_changes": datatype_changes,
    }