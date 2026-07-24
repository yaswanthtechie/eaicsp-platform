from pathlib import Path
import shutil


def quality_gate(extracted_batches):

    validated_batches = []

    rejected_folder = Path("data/rejected")
    rejected_folder.mkdir(exist_ok=True)

    for batch in extracted_batches:

        file_path = batch["file_path"]

        df = batch["data"].copy()

        null_rate = df["quantity_sold"].isna().mean()

        negative_rate = (df["quantity_sold"] < 0).mean()

        row_count = len(df)

        if null_rate >= 0.10:

            shutil.move(
                str(file_path),
                rejected_folder / file_path.name
            )

            print(
                f"{file_path.name} rejected (too many nulls)"
            )

            continue

        if negative_rate >= 0.05:

            shutil.move(
                str(file_path),
                rejected_folder / file_path.name
            )

            print(
                f"{file_path.name} rejected (negative quantity)"
            )

            continue

        if row_count < 100 or row_count > 2000:

            shutil.move(
                str(file_path),
                rejected_folder / file_path.name
            )

            print(
                f"{file_path.name} rejected (row count)"
            )

            continue

        df = df.dropna(
            subset=[
                "date",
                "sku_id",
                "warehouse_id"
            ]
        )

        df = df[df["quantity_sold"] > 0]

        df = df[df["unit_price"] > 0]

        validated_batches.append(df)

    return validated_batches