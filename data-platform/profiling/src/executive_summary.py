from pathlib import Path
import json

def generate_executive_summary(
    profiling_report,
    etl_output=None,
    validation_output=None,
):
    """
    Generate a one-paragraph plain-English executive summary
    from profiling and static platform outputs.
    """
    if not isinstance(profiling_report, dict):
        raise TypeError("profiling_report must be a dictionary")

    etl_data = _load_static_output(etl_output)
    validation_data = _load_static_output(validation_output)

    profiling_signals = _extract_profiling_signals(
        profiling_report
    )

    etl_signals = _extract_etl_signals(
        etl_data
    )

    validation_signals = _extract_validation_signals(
        validation_data
    )

    summary_parts = []

    profiling_summary = _build_profiling_summary(
        profiling_signals
    )

    if profiling_summary:
        summary_parts.append(profiling_summary)

    etl_summary = _build_etl_summary(
        etl_signals
    )

    if etl_summary:
        summary_parts.append(etl_summary)

    validation_summary = _build_validation_summary(
        validation_signals
    )

    if validation_summary:
        summary_parts.append(validation_summary)

    if not summary_parts:
        return "No platform health signals are available for this run."

    return " ".join(summary_parts)


def _extract_profiling_signals(profiling_report):
    """
    Extract the most important health signals
    from the profiling report.
    """

    quality_score = profiling_report.get(
        "quality_score",
        {},
    )

    score = quality_score.get("score")

    missing_values = quality_score.get(
        "missing_values",
        0,
    )

    duplicate_rows = quality_score.get(
        "duplicate_rows",
        0,
    )

    total_outliers = quality_score.get(
        "total_outliers",
        0,
    )

    worst_issues = profiling_report.get(
        "worst_issues",
        [],
    )

    insights = profiling_report.get(
        "insights",
        [],
    )

    return {
        "quality_score": score,
        "missing_values": missing_values,
        "duplicate_rows": duplicate_rows,
        "total_outliers": total_outliers,
        "worst_issues": worst_issues,
        "insights": insights,
    }

def _build_profiling_summary(signals):
    """
    Build a plain-English summary from profiling signals.
    """

    score = signals.get(
        "quality_score"
    )

    missing_values = signals.get(
        "missing_values",
        0,
    )

    duplicate_rows = signals.get(
        "duplicate_rows",
        0,
    )

    total_outliers = signals.get(
        "total_outliers",
        0,
    )

    parts = []

    if score is not None:
        parts.append(
            f"The latest profiling run has an "
            f"overall quality score of {score}/100."
        )

    if missing_values > 0:
        parts.append(
            f"It contains {missing_values} missing values."
        )

    if duplicate_rows > 0:
        parts.append(
            f"It contains {duplicate_rows} duplicate rows."
        )

    if total_outliers > 0:
        parts.append(
            f"It contains {total_outliers} detected outliers."
        )

    if not parts:
        return (
            "The latest profiling run did not report "
            "any major quality issues."
        )

    return " ".join(parts)

def _extract_etl_signals(etl_output):
    """
    Extract important signals from a static ETL output.
    """

    if not isinstance(etl_output, dict):
        return {}

    signals = {}

    if "status" in etl_output:
        signals["status"] = etl_output["status"]

    if "warnings" in etl_output:
        signals["warnings"] = _count(etl_output["warnings"])

    if "errors" in etl_output:
        signals["errors"] = _count(etl_output["errors"])

    if "sla_status" in etl_output:
        signals["sla_status"] = etl_output["sla_status"]

    return signals

def _count(value):
    """
    Turn a count-or-list into a number.

    Real reports list each issue (Tharun's validator writes `errors` as a
    list of {"rule", "field", "count"}); simple summaries give a number.
    Either way the summary must say "6 errors", never print the list.
    """
    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, (list, tuple, dict)):
        return len(value)

    return 0


def _extract_real_validation_report(report):
    """
    Read the report Tharun's validator actually publishes
    (data-platform/validation, `validate_cli --output report.json`).

    Its fields: passed (bool), total_rows_affected (int), errors and
    warnings (lists of {"rule", "field", "count"}), sla_breached (bool),
    batch_rejected (bool). We only READ this file; we never import or
    call the validator, so the two stay independent.
    """
    errors = report.get("errors") or []
    warnings = report.get("warnings") or []

    signals = {
        "status": "pass" if report["passed"] else "fail",
        "invalid_rows": _count(report.get("total_rows_affected", 0)),
        "errors": _count(errors),
        "warnings": _count(warnings),
    }

    # The rules that hit the most rows are what an executive needs to
    # know first, so name the top three instead of listing everything.
    worst = sorted(
        (issue for issue in errors if isinstance(issue, dict)),
        key=lambda issue: issue.get("count", 0),
        reverse=True,
    )[:3]

    if worst:
        signals["top_error_rules"] = [
            f"{issue.get('rule', 'unknown rule')} "
            f"({_count(issue.get('count', 0))} rows)"
            for issue in worst
        ]

    if report.get("sla_breached"):
        signals["sla_breached"] = True

    if report.get("batch_rejected"):
        signals["batch_rejected"] = True

    return signals


def _extract_validation_signals(validation_output):
    """
    Extract important signals from a static validation output.

    Accepts Tharun's real validator report (it has a "passed" field) or
    the simple summary shape {"status", "invalid_rows", ...}.
    """

    if not isinstance(validation_output, dict):
        return {}

    if "passed" in validation_output:
        return _extract_real_validation_report(validation_output)

    signals = {}

    if "status" in validation_output:
        signals["status"] = validation_output["status"]

    if "invalid_rows" in validation_output:
        signals["invalid_rows"] = validation_output[
            "invalid_rows"
        ]

    if "validation_failures" in validation_output:
        signals["validation_failures"] = (
            validation_output["validation_failures"]
        )

    if "errors" in validation_output:
        signals["errors"] = _count(validation_output["errors"])

    if "warnings" in validation_output:
        signals["warnings"] = _count(validation_output["warnings"])


    return signals

def _build_etl_summary(signals):
    """
    Build a plain-English summary from ETL signals.
    """
    if not signals:
        return ""

    parts = []

    if "status" in signals:
        parts.append(
            f"The ETL pipeline status is {signals['status']}"
        )

    if "sla_status" in signals:
        parts.append(
            f"Its SLA status is {signals['sla_status']}"
        )

    if "warnings" in signals and signals["warnings"]:
        count = signals["warnings"]
        label = "ETL warning" if count == 1 else "ETL warnings"
        parts.append(f"It reported {count} {label}")

    if "errors" in signals and signals["errors"]:
        count = signals["errors"]
        label = "ETL error" if count == 1 else "ETL errors"
        parts.append(f"It reported {count} {label}")

    if not parts:
        return ""

    return ". ".join(parts) + "."

def _build_validation_summary(signals):
    """
    Build a plain-English summary from validation signals.
    """
    if not signals:
        return ""

    parts = []

    if "status" in signals:
        parts.append(
            f"Validation status is {signals['status']}"
        )

    if "invalid_rows" in signals and signals["invalid_rows"]:
        count = signals["invalid_rows"]
        label = "row is invalid" if count == 1 else "rows are invalid"
        parts.append(f"{count} {label}")

    if "validation_failures" in signals and signals["validation_failures"]:
        count = signals["validation_failures"]
        label = (
            "validation failure"
            if count == 1
            else "validation failures"
        )
        parts.append(f"It reported {count} {label}")

    if "errors" in signals and signals["errors"]:
        count = signals["errors"]
        label = (
            "validation error"
            if count == 1
            else "validation errors"
        )
        parts.append(f"It reported {count} {label}")

    if "warnings" in signals and signals["warnings"]:
        count = signals["warnings"]
        label = (
            "validation warning"
            if count == 1
            else "validation warnings"
        )
        parts.append(f"It reported {count} {label}")

    if signals.get("top_error_rules"):
        parts.append(
            "The most frequent validation errors were "
            + ", ".join(signals["top_error_rules"])
        )

    if signals.get("batch_rejected"):
        parts.append("The validated batch was rejected")

    if signals.get("sla_breached"):
        parts.append("The validation SLA was breached")

    if not parts:
        return ""

    return ". ".join(parts) + "."


def _load_static_output(source):
    """
    Load a static platform output from a dictionary or JSON file.
    """
    if source is None:
        return {}

    if isinstance(source, dict):
        return source

    if isinstance(source, (str, Path)):
        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(
                f"Static output file not found: {path}"
            )

        if path.suffix.lower() != ".json":
            raise ValueError(
                "Static output file must be a JSON file"
            )

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "Static output JSON must contain an object"
            )

        return data

    raise TypeError(
        "source must be a dictionary, JSON file path, or None"
    )