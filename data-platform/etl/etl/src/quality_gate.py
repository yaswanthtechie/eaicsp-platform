from pathlib import Path
import shutil
from alert_service import write_alert
from logging_config import logger
import dead_letter


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
        "reason": ""
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

    rejected_folder = Path("data/rejected")
    rejected_folder.mkdir(parents=True, exist_ok=True)

    for batch in extracted_batches:

        file_path = batch["file_path"]
        df = batch["data"].copy()

        passed, report = check_batch(df, file_path.name)

        if not passed:

            shutil.move(str(file_path), rejected_folder / file_path.name)

            print(f"{file_path.name} rejected ({report['reason']})")
            write_alert(          
                pipeline="sales_etl",
                severity="WARN",
                message=report["reason"],
                batch_file=file_path.name
            )

            continue

        rows_before = len(df)

        df = df.dropna(
            subset=[
                "date",
                "sku_id",
                "warehouse_id"
            ]
        )

        df = df[df["quantity_sold"] > 0]
        df = df[df["unit_price"] > 0]

        report["rows_dropped"] = rows_before - len(df)

        validated_batches.append(
            {
                "data": df,
                "file_path": file_path,
                "report": report
            }
        )

    return validated_batches


def check_batch_generic(df, batch_name, source_config):
    """Same shape of check as check_batch(), but the column checked and the
    thresholds all come from the source's config (pipeline_config.yaml)
    instead of being hardcoded to sales' quantity_sold."""

    column = source_config.quality_check_column

    null_rate = df[column].isna().mean()
    negative_rate = (df[column] < 0).mean()
    row_count = len(df)

    report = {
        "batch_name": batch_name,
        "rows": row_count,
        "null_rate": null_rate,
        "negative_rate": negative_rate,
        "rows_dropped": 0,
        "reason": ""
    }

    if null_rate >= source_config.null_rate_threshold:
        report["reason"] = "too many nulls"
        return False, report

    if negative_rate >= source_config.negative_rate_threshold:
        report["reason"] = f"negative {column}"
        return False, report

    if row_count < source_config.min_rows or row_count > source_config.max_rows:
        report["reason"] = "invalid row count"
        return False, report

    return True, report


def quality_gate_generic(extracted_batches, source_config):
    """Config-driven quality gate used by the generic pipeline engine for any
    source. Includes the dead-letter stretch goal: a filename that fails 3
    runs in a row is moved to data/needs_manual_review/ instead of being
    silently rejected every night forever."""

    validated_batches = []

    rejected_folder = Path("data/rejected")
    rejected_folder.mkdir(parents=True, exist_ok=True)

    manual_review_folder = Path("data/needs_manual_review")
    manual_review_folder.mkdir(parents=True, exist_ok=True)

    required_cols = [
        col for col, rule in source_config.columns.items()
        if rule.get("required")
    ]

    for batch in extracted_batches:

        file_path = batch["file_path"]
        df = batch["data"].copy()

        passed, report = check_batch_generic(df, file_path.name, source_config)

        if not passed:

            failure_count = dead_letter.record_failure(file_path.name)

            if failure_count >= dead_letter.DEAD_LETTER_THRESHOLD:

                shutil.move(str(file_path), manual_review_folder / file_path.name)

                logger.error(
                    f"{file_path.name} failed quality gate "
                    f"{failure_count} times in a row - moved to "
                    f"needs_manual_review/ ({report['reason']})"
                )

                write_alert(
                    pipeline="sales_etl",
                    severity="CRITICAL",
                    message=(
                        f"{report['reason']} - dead-lettered after "
                        f"{failure_count} consecutive failures"
                    ),
                    batch_file=file_path.name
                )

                dead_letter.clear_failures(file_path.name)

            else:

                shutil.move(str(file_path), rejected_folder / file_path.name)

                logger.warning(
                    f"{file_path.name} rejected ({report['reason']}), "
                    f"failure #{failure_count}"
                )

                write_alert(
                    pipeline="sales_etl",
                    severity="WARN",
                    message=report["reason"],
                    batch_file=file_path.name
                )

            continue

        dead_letter.clear_failures(file_path.name)

        rows_before = len(df)

        df = df.dropna(subset=required_cols)

        column = source_config.quality_check_column
        df = df[df[column] > 0]

        report["rows_dropped"] = rows_before - len(df)

        validated_batches.append(
            {
                "data": df,
                "file_path": file_path,
                "report": report
            }
        )

    return validated_batches