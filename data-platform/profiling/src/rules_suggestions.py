from pathlib import Path
from src.relationships import discover_relationships

import yaml


RULES_VERSION = "1.0.0"
VALID_RULE_TYPES = {
    "not_null",
    "range",
    "regex",
    "unique",
    "custom",
    "transform",
    "relationship_match",
}
VALID_SEVERITIES = {
    "ERROR",
    "WARNING",
    "INFO",
}


def _build_rule_name(column_name, rule_type):
    """Create a deterministic rule name."""
    return f"{column_name}_{rule_type}"

def suggest_relationship_rules(
    df_left,
    df_right,
):
    """
    Generate validation rules from discovered dataset relationships.

    Only likely join-key relationships are converted into
    relationship-based validation rules.
    """

    relationships = discover_relationships(
        df_left,
        df_right,
    )

    relationship_rules = []

    for relationship in relationships:

        if relationship["classification"] != "likely_join_key":
            continue

        left_column = relationship["left_column"]
        right_column = relationship["right_column"]

        relationship_rules.append({
            "name": (
                f"{left_column}_relationship_{right_column}"
            ),
            "type": "relationship_match",
            "left_field": left_column,
            "right_field": right_column,
            "overlap_percentage": relationship[
                "overlap_percentage"
            ],
            "severity": "ERROR",
        })

    return relationship_rules


def suggest_rules(
    report,
    null_threshold_percentage_points=0.2,
    df_left=None,
    df_right=None,
):
    """
    Generate data-quality rules from profiling results.

    The returned structure follows the validation library's
    documented YAML configuration format.
    """

    if not isinstance(report, dict):
        raise TypeError("report must be a dictionary")

    if null_threshold_percentage_points < 0:
        raise ValueError(
            "null_threshold_percentage_points must be non-negative"
        )

    rules = []

    column_summary = report.get("column_summary", [])
    statistics = report.get("statistics", {})
    outliers = report.get("outliers", {})

    for column in column_summary:

        name = column["column"]
        null_percent = float(column["null_percent"])
        dtype = column["dtype"]

        # ---------------------------------
        # not_null rule
        # ---------------------------------
        if null_percent <= null_threshold_percentage_points:

            rules.append({
                "name": _build_rule_name(name, "not_null"),
                "field": name,
                "type": "not_null",
                "severity": "ERROR",
            })

        # ---------------------------------
        # range rule for numeric columns
        # ---------------------------------
        if dtype.startswith(("int", "float")):

            stats = statistics.get(name, {})
            outlier_info = outliers.get(name, {})

            min_value = stats.get("min")
            max_value = stats.get("max")

            lower_limit = outlier_info.get("lower_limit")
            upper_limit = outlier_info.get("upper_limit")

            # Use IQR limits when available so detected
            # outliers are not included in the suggested range.
            if (
                min_value is not None
                and max_value is not None
                and lower_limit is not None
                and upper_limit is not None
            ):
                suggested_min = max(
                    float(min_value),
                    float(lower_limit),
                )

                suggested_max = min(
                    float(max_value),
                    float(upper_limit),
                )

            # Fall back to the observed min/max.
            elif (
                min_value is not None
                and max_value is not None
            ):
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
                    "name": _build_rule_name(name, "range"),
                    "field": name,
                    "type": "range",
                    "min": suggested_min,
                    "max": suggested_max,
                    "severity": "WARNING",
                })

    relationship_rules = []

    if df_left is not None and df_right is not None:
        relationship_rules = suggest_relationship_rules(
            df_left,
            df_right,
        )

    return {
        "version": RULES_VERSION,
        "rules": rules,
        "relationship_rules": relationship_rules,
    }


def validate_rules_config(config):
    """
    Independently validate the generated rule configuration.

    This checks the documented configuration structure without
    importing or executing the validation library.
    """

    if not isinstance(config, dict):
        raise ValueError("Rules configuration must be a dictionary")

    if config.get("version") != RULES_VERSION:
        raise ValueError(
            f"Unsupported or missing version: {config.get('version')}"
        )

    rules = config.get("rules")

    if not isinstance(rules, list):
        raise ValueError("'rules' must be a list")

    for index, rule in enumerate(rules):

        if not isinstance(rule, dict):
            raise ValueError(
                f"Rule at index {index} must be a dictionary"
            )

        required_fields = {
            "name",
            "type",
            "severity",
        }

        missing = required_fields - rule.keys()

        if missing:
            raise ValueError(
                f"Rule at index {index} is missing: "
                f"{sorted(missing)}"
            )

        rule_type = rule["type"]
        severity = rule["severity"]

        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                f"Invalid rule type '{rule_type}' "
                f"at index {index}"
            )

        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}' "
                f"at index {index}"
            )

        # Standard rules require a target field.
        if rule_type not in {"custom", "transform"}:
            if not rule.get("field"):
                raise ValueError(
                    f"Rule '{rule['name']}' requires 'field'"
                )

        # Range rules require min/max information.
        if rule_type == "range":

            if "min" not in rule and "max" not in rule:
                raise ValueError(
                    f"Range rule '{rule['name']}' "
                    "must contain 'min' or 'max'"
                )

            if "min" in rule and "max" in rule:
                if rule["min"] > rule["max"]:
                    raise ValueError(
                        f"Range rule '{rule['name']}' "
                        "has min greater than max"
                    )

    relationship_rules = config.get(
        "relationship_rules",
        []
    )

    if not isinstance(relationship_rules, list):
        raise ValueError(
            "'relationship_rules' must be a list"
        )

    for index, rule in enumerate(relationship_rules):

        if not isinstance(rule, dict):
            raise ValueError(
                f"Relationship rule at index {index} "
                "must be a dictionary"
            )

        required_fields = {
            "name",
            "type",
            "left_field",
            "right_field",
            "overlap_percentage",
            "severity",
        }

        missing = required_fields - rule.keys()

        if missing:
            raise ValueError(
                f"Relationship rule at index {index} "
                f"is missing: {sorted(missing)}"
            )

        if rule["type"] != "relationship_match":
            raise ValueError(
                f"Invalid relationship rule type "
                f"'{rule['type']}' at index {index}"
            )

        if not rule["left_field"]:
            raise ValueError(
                f"Relationship rule '{rule['name']}' "
                "requires 'left_field'"
            )

        if not rule["right_field"]:
            raise ValueError(
                f"Relationship rule '{rule['name']}' "
                "requires 'right_field'"
            )

        if rule["severity"] not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{rule['severity']}' "
                f"at relationship rule index {index}"
            )

        overlap = rule["overlap_percentage"]

        if not isinstance(overlap, (int, float)):
            raise ValueError(
                f"Invalid overlap percentage at "
                f"relationship rule index {index}"
            )

        if not 0 <= overlap <= 100:
            raise ValueError(
                f"Overlap percentage must be between 0 and 100 "
                f"at relationship rule index {index}"
            )

    return True


def write_rules_yaml(
    report,
    output_path="reports/suggested_rules.yaml",
    null_threshold_percentage_points=0.2,
    df_left=None,
    df_right=None,
):
    """
    Generate Tharun-compatible rules and write them to YAML.

    The generated configuration is independently validated before
    it is written to disk.
    """

    
    rules_config = suggest_rules(
        report,
        null_threshold_percentage_points=null_threshold_percentage_points,
        df_left=df_left,
        df_right=df_right,
    )
    # Validate the Python representation first.
    validate_rules_config(rules_config)

    output_path = Path(output_path)

    # Create parent directory if necessary.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        yaml.safe_dump(
            rules_config,
            file,
            sort_keys=False,
        )

    return output_path