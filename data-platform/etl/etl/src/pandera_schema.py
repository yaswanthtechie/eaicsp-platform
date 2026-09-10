import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema


sales_schema = DataFrameSchema(
    {
        "date": Column(pa.DateTime),
        "sku_id": Column(str),
        "warehouse_id": Column(str),
        "quantity_sold": Column(
            int,
            checks=pa.Check.ge(0)
        ),
        "unit_price": Column(
            float,
            checks=pa.Check.gt(0),
            coerce=True
        ),
    },
    strict=False
)


def validate_with_pandera(df):

    sales_schema.validate(df)

    return df