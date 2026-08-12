from pathlib import Path
import shutil

from alert_service import write_alert


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REJECTED_DIR = PROJECT_ROOT / "data" / "rejected"


def check_batch(df, batch_name):

    null_rate = df["quantity_sold"].isna().mean()
    negative_rate = (df["quantity_sold"] < 0).mean()
    row_count = len(df)

    report = {
        "batch_name": batch_name,
        "rows": row_count,
        "null_rate": null_rate,
        "negative_rate": negative_rate,
        "rows_dropped": 0,
        "reason": "",
    }

    if null_rate >= 0.10:
        report["reason"] = "too many nulls"
        return False, report

    if negative_rate >= 0.05:
        report["reason"] = "negative quantity"
        return False, report

    if row_count < 5 or row_count > 2000:
        report["reason"] = "invalid row count"
        return False, report

    return True, report


def quality_gate(extracted_batches):

    validated_batches = []

    rejected_folder = REJECTED_DIR
    rejected_folder.mkdir(parents=True, exist_ok=True)

    try:

        for batch in extracted_batches:

            file_path = batch["file_path"]
            df = batch["data"].copy()

            passed, report = check_batch(
                df,
                file_path.name,
            )

            if not passed:

                shutil.move(
                    str(file_path),
                    rejected_folder / file_path.name,
                )

                print(
                    f"{file_path.name} rejected "
                    f"({report['reason']})"
                )

                write_alert(
                    pipeline="sales_etl",
                    severity="WARN",
                    message=report["reason"],
                    batch_file=file_path.name,
                )

                continue

            rows_before = len(df)

            df = df.dropna(
                subset=[
                    "date",
                    "sku_id",
                    "warehouse_id",
                ]
            )

            df = df[df["quantity_sold"] > 0]
            df = df[df["unit_price"] > 0]

            report["rows_dropped"] = (
                rows_before - len(df)
            )

            validated_batches.append(
                {
                    "data": df,
                    "file_path": file_path,
                    "report": report,
                }
            )

        return validated_batches

    except Exception as e:

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Quality gate stage failed: {e}",
        )

        raise