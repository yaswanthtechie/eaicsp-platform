import sys
import json
import argparse
import logging
import math
from pathlib import Path
from collections import Counter
from typing import Dict, Any, Union, Optional
from datetime import datetime

import pandas as pd

from src.validator import DataValidator

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any) -> Any:
    """Recursively replaces NaNs with None for safe JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"folder_validation_{timestamp}.log"

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger.info("Logging initialized. Writing logs to: %s", log_file)


def _load_validator(config_path: str, cache: dict) -> DataValidator:
    if config_path not in cache:
        logger.debug("Initializing new DataValidator for config: %s", config_path)
        cache[config_path] = DataValidator.from_config(config_path)
    return cache[config_path]


def validate_folder(
        folder_path: Union[str, Path],
        config_path: Optional[Union[str, Path]] = None,
        mapping_path: Optional[Union[str, Path]] = None,
        default_pattern: str = "*.csv",
        top_n_issues: int = 3,
        output_dir: str = "reports",
        save_reports: bool = False,
        incremental: bool = False,
        watermark_col: str = "transaction_id",
        watermark_dir: str = ".watermarks"
) -> Dict[str, Any]:
    folder = Path(folder_path)

    if not folder.is_dir():
        raise NotADirectoryError(f"Data folder not found: {folder}")
    if not config_path and not mapping_path:
        raise ValueError("Either 'config_path' or 'mapping_path' must be provided.")

    if save_reports:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    validators_cache: Dict[str, DataValidator] = {}
    validation_queue: Dict[Path, DataValidator] = {}

    if mapping_path:
        mapping_file = Path(mapping_path)
        if not mapping_file.is_file():
            raise FileNotFoundError(f"Mapping file not found: {mapping_file}")

        with open(mapping_file, 'r') as f:
            mapping_rules = json.load(f)

        for pattern, cfg_path in mapping_rules.items():
            validator = _load_validator(cfg_path, validators_cache)
            for file_path in folder.rglob(pattern):
                validation_queue[file_path] = validator

        logger.info("Loaded %d routing rules from %s", len(mapping_rules), mapping_file.name)
    else:
        if not Path(config_path).is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        validator = _load_validator(str(config_path), validators_cache)
        for file_path in folder.rglob(default_pattern):
            validation_queue[file_path] = validator

    if not validation_queue:
        logger.warning("No files found matching the provided patterns in %s", folder)
        return {}

    summary: Dict[str, Any] = {
        "total_files": len(validation_queue),
        "passed_files": 0,
        "failed_files": 0,
        "total_rows_affected": 0,
        "most_common_issues": Counter()
    }

    # --- Setup Watermark Directory if Incremental ---
    if incremental:
        from src.watermark import WatermarkManager
        wm_dir = Path(watermark_dir)
        wm_dir.mkdir(parents=True, exist_ok=True)

    for file_path, validator in validation_queue.items():
        logger.info("Validating %s...", file_path.name)
        try:
            df = pd.read_csv(file_path, memory_map=True)
            # --- Incremental Filtering per file ---
            wm = None
            if incremental:
                wm_file = wm_dir / f"{file_path.stem}_watermark.json"
                wm = WatermarkManager(wm_file)
                current_wm = wm.get_watermark()

                df = DataValidator.filter_incremental(df, watermark_col, current_wm)

                if df.empty:
                    logger.info("   -> Skipped: No new incremental data.")
                    summary["passed_files"] += 1
                    continue
                logger.info("   -> Validating %d new rows...", len(df))
            # --- Validation ---
            report = validator.validate(df)

            passed = getattr(report, 'passed', False)
            if passed:
                summary["passed_files"] += 1
            else:
                summary["failed_files"] += 1

            summary["total_rows_affected"] += getattr(report, 'total_rows_affected', 0)

            for error in getattr(report, 'errors', []):
                rule = error.get("rule", "unknown_rule")
                count = error.get("count", 1)
                summary["most_common_issues"][rule] += count

            # --- Export Report ---
            if save_reports:
                # Wrap the entire dictionary in the sanitizer before dumping
                file_report_data = sanitize_for_json({
                    "config_version": getattr(report, "config_version", "1.0.0"),
                    "passed": passed,
                    "total_rows_affected": getattr(report, "total_rows_affected", 0),
                    "errors": getattr(report, "errors", []),
                    "warnings": getattr(report, "warnings", []),
                    "sample_bad_rows": getattr(report, "sample_bad_rows", {})
                })

                report_filename = out_path / f"{file_path.stem}_report.json"
                with open(report_filename, 'w', encoding='utf-8') as f:
                    json.dump(file_report_data, f, indent=2)
                logger.debug("Saved detailed report to %s", report_filename)

            # --- Update File-Specific Watermark ---
            if incremental and wm is not None and not df.empty:
                new_wm = df[watermark_col].max()
                new_wm = new_wm.item() if hasattr(new_wm, 'item') else new_wm
                wm.set_watermark(new_wm)

        except pd.errors.EmptyDataError:
            logger.warning("Skipped empty file: %s", file_path.name)
            summary["failed_files"] += 1
        except Exception as e:
            logger.error("Failed to process %s: %s", file_path.name, e)
            summary["failed_files"] += 1

    summary["most_common_issues"] = dict(summary["most_common_issues"].most_common(top_n_issues))

    logger.info("\n--- AGGREGATE SUMMARY ---")
    logger.info("%d of %d files passed.", summary['passed_files'], summary['total_files'])

    if summary['most_common_issues']:
        top_issue = next(iter(summary['most_common_issues']))
        logger.info("Top issue: %s", top_issue)

    if save_reports:
        summary_filename = out_path / "aggregate_summary.json"
        with open(summary_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        logger.info("Saved aggregate summary to %s", summary_filename)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Validate a folder of data files.")
    parser.add_argument("--folder", type=str, required=True, help="Path to the data folder.")
    parser.add_argument("--pattern", type=str, default="*.csv", help="File pattern to match.")
    parser.add_argument("--top-n", type=int, default=3, help="Number of top error rules to summarize.")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-dir", type=str, default="logs", help="Directory to save timestamped log files.")
    parser.add_argument("--save-reports", action="store_true",
                        help="Enable generating and saving detailed JSON reports.")
    parser.add_argument("--output-dir", type=str, default="reports", help="Directory to save detailed JSON reports.")
    # --- INCREMENTAL ARGUMENTS ---
    parser.add_argument("--incremental", action="store_true", help="Only process new rows since the last run.")
    parser.add_argument("--watermark-col", type=str, default="transaction_id", help="Column for watermarking.")
    parser.add_argument("--watermark-dir", type=str, default=".watermarks", help="Directory for state tracking files.")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", type=str, help="Path to a single validation YAML configuration file.")
    group.add_argument("--mapping", type=str, help="Path to a JSON file mapping glob patterns to config files.")

    args = parser.parse_args()
    setup_logging(log_level=args.log_level, log_dir=args.log_dir)

    try:
        validate_folder(
            folder_path=args.folder,
            config_path=args.config,
            mapping_path=args.mapping,
            default_pattern=args.pattern,
            top_n_issues=args.top_n,
            output_dir=args.output_dir,
            save_reports=args.save_reports,
            incremental=args.incremental,
            watermark_col=args.watermark_col,
            watermark_dir=args.watermark_dir
        )
    except Exception as e:
        logger.critical("Validation pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()