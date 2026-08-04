import logging

logger = logging.getLogger(__name__)

EXPECTED_SCHEMA = {
    "date": {
        "type": "datetime64[us]",
        "required": True
    },
    "sku_id": {
        "type": "str",
        "required": True
    },
    "warehouse_id": {
        "type": "str",
        "required": True
    },
    "quantity_sold": {
        "type": "int64",
        "required": True
    },
    "unit_price": {
        "type": "int64",
        "required": True
    },
}


def validate_schema(df):


    for column, rule in EXPECTED_SCHEMA.items():

        if rule["required"] and column not in df.columns:

            logger.error(f"Missing required column : {column}")

            raise ValueError(
                f"Missing required column : {column}"
            )

   

    for column, rule in EXPECTED_SCHEMA.items():

        if column not in df.columns:
            continue

        actual = str(df[column].dtype)

        if actual != rule["type"]:

            logger.error(
                f"{column} datatype mismatch. "
                f"Expected={rule['type']} "
                f"Actual={actual}"
            )

            raise TypeError(
                f"{column} datatype mismatch"
            )

    

    for column in df.columns:

        if column not in EXPECTED_SCHEMA:

            logger.warning(
                f"Unexpected column detected : {column}"
            )

    logger.info("Schema validation passed")

    return True