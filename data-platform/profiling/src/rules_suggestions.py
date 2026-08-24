import yaml


def suggest_rules(report, null_threshold=0.2):
    """
    Generate suggested data-quality rules from profiling results.

    Suggestions are informational only and are not connected
    to any external rules engine.
    """

    rules = []

    column_summary = report.get("column_summary", [])
    statistics = report.get("statistics", {})
    outliers = report.get("outliers", {})

    for column in column_summary:
        name = column["column"]
        null_percent = float(column["null_percent"])
        dtype = column["dtype"]

        # Suggest not_null for columns with very low null rate
        if null_percent <= null_threshold:
            rules.append({
                "column": name,
                "rule": "not_null"
            })

        # Suggest range rule for numeric columns
        if dtype.startswith(("int", "float")):
            stats = statistics.get(name, {})
            outlier_info = outliers.get(name, {})

            min_value = stats.get("min")
            max_value = stats.get("max")

            lower_limit = outlier_info.get("lower_limit")
            upper_limit = outlier_info.get("upper_limit")

            # Use IQR upper limit to exclude detected outliers.
            if (
                min_value is not None
                and max_value is not None
                and lower_limit is not None
                and upper_limit is not None
            ):
                suggested_min = max(
                    float(min_value),
                    float(lower_limit)
                )

                suggested_max = min(
                    float(max_value),
                    float(upper_limit)
                )

            # Fallback to the original min/max if
            # outlier information is unavailable.
            elif min_value is not None and max_value is not None:
                suggested_min = float(min_value)
                suggested_max = float(max_value)

            else:
                suggested_min = None
                suggested_max = None

            if (
                suggested_min is not None
                and suggested_max is not None
                and suggested_min <= suggested_max
            ):
                rules.append({
                    "column": name,
                    "rule": "range",
                    "min": suggested_min,
                    "max": suggested_max
                })

    return {"rules": rules}


def write_rules_yaml(
    report,
    output_path="reports/suggested_rules.yaml",
    null_threshold=0.2
):
    """
    Generate suggested rules and write them to a YAML file.
    """

    rules = suggest_rules(
        report,
        null_threshold=null_threshold
    )

    with open(output_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(
            rules,
            file,
            sort_keys=False
        )

    return output_path