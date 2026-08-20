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

            min_value = stats.get("min")
            max_value = stats.get("max")

            if min_value is not None and max_value is not None:
                rules.append({
                    "column": name,
                    "rule": "range",
                    "min": float(min_value),
                    "max": float(max_value)
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