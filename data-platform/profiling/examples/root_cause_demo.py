from pathlib import Path

import pandas as pd

from src.relationships import discover_relationships
from src.root_cause import suggest_root_causes


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def main():
    # ---------------------------------
    # Load existing project datasets
    # ---------------------------------
    sales = pd.read_csv(DATA_DIR / "sales_data.csv")
    products = pd.read_csv(DATA_DIR / "products_data.csv")

    # Remove the deliberately injected 99999 outlier
    # so that the demo focuses on normal sales behavior.
    sales = sales[sales["quantity_sold"] < 5000].copy()

    # ---------------------------------
    # Create old snapshots
    # ---------------------------------
    sales_old = sales.copy()
    products_old = products.copy()

    # ---------------------------------
    # Create new product snapshot
    # ---------------------------------
    products_new = products.copy()

    skus = sorted(products_new["sku_id"].unique())

    # Simulate a substantial price increase
    # across products.
    factors = {
        sku: 2.0 + (3.0 * index / (len(skus) - 1))
        for index, sku in enumerate(skus)
    }
    products_new["unit_price"] = (
        products_new["unit_price"]
        * products_new["sku_id"].map(factors)
    )

    # ---------------------------------
    # Create new sales snapshot
    # ---------------------------------
    sales_new = sales.copy()

    # Simulate quantity decreasing as product price increases.
    sales_new["quantity_sold"] = (
        sales_new["quantity_sold"]
        * sales_new["sku_id"].map(
            {sku: 1 / factor for sku, factor in factors.items()}
        )
    )

    # ---------------------------------
    # Discover relationship
    # ---------------------------------
    relationships = discover_relationships(
        sales_new,
        products_new,
    )

    print("\n=== RELATIONSHIPS ===")

    for relationship in relationships:
        print(relationship)

    # ---------------------------------
    # Suggest root causes
    # ---------------------------------
    candidates = suggest_root_causes(
        downstream_old=sales_old,
        downstream_new=sales_new,
        upstream_old=products_old,
        upstream_new=products_new,
        relationships=relationships,
    )

    print("\n=== ROOT-CAUSE SUGGESTIONS ===")

    if not candidates:
        print("No plausible root cause found.")
        return

    for candidate in candidates:
        print("\nDownstream metric:")
        print(candidate["downstream_metric"])

        print("\nUpstream metric:")
        print(candidate["upstream_metric"])

        print("\nRelationship:")
        print(candidate["relationship"])

        print("\nCorrelation:")
        print(candidate["correlation"])

        print("\nMatched keys:")
        print(candidate["matched_keys"])

        print("\nSuggestion:")
        print(candidate["suggestion"])


if __name__ == "__main__":
    main()