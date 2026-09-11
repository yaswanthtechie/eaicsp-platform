import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.validator import DataValidator, SAFE_FUNCTION_REGISTRY


def get_human_readable_description(rule) -> str:
    """Gets the description from the YAML or falls back to auto-generated/docstrings."""
    # 1. User-provided description in YAML (Highest Priority)
    if hasattr(rule, 'description') and rule.description:
        return rule.description.strip()

    # 2. Auto-generate basic descriptions for standard types
    if rule.type == "not_null":
        return "Must not be empty or null."
    elif rule.type == "regex":
        pattern = (rule.model_extra or {}).get("pattern", "unknown")
        return f"Must strictly match the regex pattern: `{pattern}`"
    elif rule.type == "range":
        extra = rule.model_extra or {}
        min_val = extra.get('min', '-∞')
        max_val = extra.get('max', '∞')
        return f"Value must be between **{min_val}** and **{max_val}**."
    elif rule.type == "unique":
        return "Value must be unique across the entire dataset."
    elif rule.type == "conditional":
        extra = rule.model_extra or {}
        cond_f = extra.get('condition_field', 'X')
        cond_v = extra.get('condition_value', 'Y')
        return f"If `{cond_f}` == '{cond_v}', secondary validation rules apply."

    # 3. Fallback to Python Docstrings for custom/transform functions
    elif rule.type in ["custom", "transform"]:
        func_path = (rule.model_extra or {}).get('function')
        if func_path and func_path in SAFE_FUNCTION_REGISTRY:
            doc = SAFE_FUNCTION_REGISTRY[func_path].__doc__
            if doc:
                return f"*(Custom)* {doc.strip()}"
        return f"Applies custom {rule.type} logic."

    return "Standard validation rule."


def generate_markdown_for_profile(validator: DataValidator, profile_name: str) -> str:
    """Generates the Markdown contract for a specific, flattened profile."""

    md = [
        f"# Data Quality Contract: `{profile_name}` profile",
        f"*Auto-generated from config version: {validator.version}*\n",
        "---",
        "## 1. Data Shape & Business Rules",
        "This section defines what constitutes a 'valid' row in this dataset.\n",
        "| Field | Rule Name | Type | Severity | Description |",
        "|---|---|---|---|---|"
    ]

    # Section 1: Business Rules
    for rule in validator.rules:
        field_name = f"`{rule.field}`" if rule.field else "*Cross-field/Dataset*"
        desc = get_human_readable_description(rule)
        md.append(f"| {field_name} | `{rule.name}` | `{rule.type}` | {rule.severity} | {desc} |")

    # Section 2: SLAs & Thresholds
    md.extend([
        "\n---",
        "## 2. Operational SLAs & Pipeline Thresholds",
        "This section defines the conditions under which the validation pipeline will trigger alerts or halt entirely.\n",
        "### Global Settings"
    ])

    global_fail = f"{validator.global_max_fail_pct * 100}%" if validator.global_max_fail_pct else "Not configured"
    md.extend([
        f"- **Max Batch Failure (Rejection Limit):** {global_fail}",
        f"- **Global Drift Alert (Absolute):** {validator.global_drift_abs_min * 100}% minimum failure jump",
        f"- **Global Drift Alert (Relative):** {validator.global_drift_rel_min * 100}% relative increase\n",
        "### Rule-Specific Thresholds",
        "| Rule Name | Max Fail Limit | Drift Abs Limit | Drift Rel Limit |",
        "|---|---|---|---|"
    ])

    has_sla_rules = False
    for rule in validator.rules:
        if rule.max_fail_pct or rule.drift_abs_min or rule.drift_rel_min:
            has_sla_rules = True
            m_fail = f"{rule.max_fail_pct * 100}%" if rule.max_fail_pct else "*(Global)*"
            d_abs = f"{rule.drift_abs_min * 100}%" if rule.drift_abs_min else "*(Global)*"
            d_rel = f"{rule.drift_rel_min * 100}%" if rule.drift_rel_min else "*(Global)*"
            md.append(f"| `{rule.name}` | {m_fail} | {d_abs} | {d_rel} |")

    if not has_sla_rules:
        md.append("| *(All rules)* | *(Global)* | *(Global)* | *(Global)* |")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate human-readable Markdown docs from validation configs.")
    parser.add_argument("--config", type=Path, required=True, help="Path to the YAML config file.")
    parser.add_argument("--output-dir", type=Path, default=Path("docs"), help="Directory to save the markdown files.")

    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config file {args.config} not found.")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. List all available profiles in the config
    profiles = DataValidator.list_profiles(str(args.config))
    if not profiles:
        print(f"No profiles found in {args.config}.")
        sys.exit(1)

    print(f"Found profiles: {', '.join(profiles)}")

    # 2. Generate flattened documentation for each profile
    for profile in profiles:
        try:
            # DataValidator handles inheritance seamlessly
            validator = DataValidator.from_config(str(args.config), profile_name=profile)
            markdown_content = generate_markdown_for_profile(validator, profile)

            output_file = args.output_dir / f"data_contract_{profile}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            print(f"Successfully generated: {output_file}")

        except Exception as e:
            print(f"Failed to generate docs for profile '{profile}': {e}")


if __name__ == "__main__":
    main()