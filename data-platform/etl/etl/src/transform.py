import pandas as pd


def transform_data(data_frames):

    transformed_data = []

    for df in data_frames:

        clean_df = df.copy()

        clean_df = clean_df.drop_duplicates()

        clean_df["date"] = pd.to_datetime(clean_df["date"])

        clean_df["quantity_sold"] = clean_df["quantity_sold"].astype(int)

        clean_df["unit_price"] = clean_df["unit_price"].astype(float)

        transformed_data.append(clean_df)

    return transformed_data