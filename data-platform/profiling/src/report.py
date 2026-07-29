from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from src.profile import profile
from src.outliers import find_outliers


def generate_report():

    BASE_DIR = Path(__file__).resolve().parent.parent

    DATA_PATH = BASE_DIR / "data" / "sales_data.csv"
    REPORTS_DIR = BASE_DIR / "reports"

    REPORTS_DIR.mkdir(exist_ok=True)

    df = pd.read_csv(DATA_PATH)


    df["date"] = pd.to_datetime(df["date"])


    # DATA QUALITY REPORT


    print("=" * 60)
    print("                 DATA QUALITY REPORT")
    print("=" * 60)

    print(f"Rows            : {len(df)}")
    print(f"Columns         : {len(df.columns)}")
    print(f"Date Range      : {df['date'].min().date()}  →  {df['date'].max().date()}")
    print(f"Duplicate Rows  : {df.duplicated().sum()}")

    print("\nCOLUMN SUMMARY")
    print("-" * 80)
    print(f"{'Column':<18}{'Type':<15}{'Nulls':<10}{'Null %':<10}{'Unique':<10}{'Min':<12}{'Max':<12}")
    print("-" * 80) 

    for col in df.columns:

        dtype = str(df[col].dtype)
        nulls = df[col].isna().sum()
        null_percent = round((nulls / len(df)) * 100, 2)
        unique = df[col].nunique()

        if pd.api.types.is_numeric_dtype(df[col]): # Panda module
            min_val = df[col].min()
            max_val = df[col].max()
        else:
            min_val = "-"
            max_val = "-"

        print(
            f"{col:<18}"
            f"{dtype:<15}"
            f"{nulls:<10}"
            f"{null_percent:<10}"
            f"{unique:<10}"
            f"{str(min_val):<12}"
            f"{str(max_val):<12}"
        )


# SUMMARY STATISTICS


    print("\n" + "=" * 60)
    print("QUANTITY SOLD STATISTICS")
    print("=" * 60)

    print(df["quantity_sold"].describe()) # Describe everything about column

# OUTLIER DETECTION (IQR METHOD)

    result = find_outliers(df["quantity_sold"])

    lower_limit = result["lower_limit"]
    upper_limit = result["upper_limit"]

    outliers = df[result["outlier_mask"]]


    print("\n" + "=" * 60)
    print("OUTLIER REPORT")
    print("=" * 60)

    print(f"IQR Lower Bound : {lower_limit:.2f}") # 2 decimal places
    print(f"IQR Upper Bound : {upper_limit:.2f}")
    print(f"Outliers Found  : {len(outliers)}")

    if len(outliers) > 0:
        print("\nTop Outliers:")
        print(outliers[["quantity_sold"]].head(10))


    # HISTOGRAM BEFORE REMOVING OUTLIERS


    plt.figure(figsize=(8, 5))

    plt.hist(df["quantity_sold"].dropna(), bins=20) # Removing Nan values

    plt.title("Quantity Sold Distribution (Before Removing Outliers)")
    plt.xlabel("Quantity Sold")
    plt.ylabel("Frequency")

    plt.tight_layout() # Automatically adjusts the spacing of the graph

    plt.savefig(REPORTS_DIR / "histogram_before.png")
    plt.close()



# REMOVE OUTLIERS


    clean_df = df[
        (df["quantity_sold"] >= lower_limit) &
        (df["quantity_sold"] <= upper_limit)
    ]


# HISTOGRAM AFTER REMOVING OUTLIERS


    plt.figure(figsize=(8, 5))

    plt.hist(clean_df["quantity_sold"].dropna(), bins=20) #

    plt.title("Quantity Sold Distribution (After Removing Outliers)")
    plt.xlabel("Quantity Sold")
    plt.ylabel("Frequency")

    plt.tight_layout()

    plt.savefig(REPORTS_DIR / "histogram_after.png")
    plt.close()


# BOXPLOT


    plt.figure(figsize=(8, 5))

    plt.boxplot(df["quantity_sold"].dropna())

    plt.title("Box Plot of Quantity Sold")
    plt.ylabel("Quantity Sold")

    plt.tight_layout()

    plt.savefig(REPORTS_DIR / "boxplot.png")
    plt.close()


# FINAL MESSAGE


    print("\n" + "=" * 60)
    print("REPORT GENERATED SUCCESSFULLY")
    print("=" * 60)

    print("Graphs saved in the reports folder:")
    print("histogram_before.png")
    print("histogram_after.png")
    print("boxplot.png")

if __name__ == "__main__":
    generate_report()