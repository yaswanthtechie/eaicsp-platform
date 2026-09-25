from pathlib import Path

import pandas as pd

from src.feature_catalog import generate_feature_catalog


df = pd.DataFrame({
    "date": pd.date_range("2024-01-01", periods=30),
    "target": range(30),
})

config = {
    "lags": [1, 7, 30],
    "windows": [7, 30],
}

catalogs = []

for feature_version in ["v1", "v2"]:
    catalog = generate_feature_catalog(
        df=df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version=feature_version,
    )
    catalogs.append(catalog)

catalog = pd.concat(
    catalogs,
    ignore_index=True,
)

project_root = Path(__file__).resolve().parents[1]
output_path = project_root / "docs" / "feature_catalog.md"
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", encoding="utf-8") as file:
    file.write("# Feature Catalog\n\n")
    file.write("| Feature | Type | Meaning | Version |\n")
    file.write("|---|---|---|---|\n")

    for _, row in catalog.iterrows():
        file.write(
            f"| {row['feature']} | {row['type']} | "
            f"{row['meaning']} | {row['version']} |\n"
        )

print(f"Feature catalog generated: {output_path}")