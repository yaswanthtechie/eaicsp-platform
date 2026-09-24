import argparse
import logging
import sys
import html
import re
from pathlib import Path
from typing import Dict

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.validator import DataValidator
from src.registry import RULE_REGISTRY


def get_human_readable_description(rule) -> str:
    """Gets the description from the YAML or falls back to auto-generated/docstrings."""
    # 1. Always prioritize explicit descriptions written in the YAML
    if hasattr(rule, 'description') and rule.description:
        return rule.description.strip()

    if rule.type == "not_null":
        return "Must not be empty or null."

    elif rule.type == "regex":
        pattern = (rule.model_extra or {}).get("pattern", "unknown")
        if pattern == "unknown":
            return "Must match a specific format."

        # 2. Dynamically translate regex concepts into plain English
        exact_match = pattern.startswith('^') and pattern.endswith('$')
        desc = pattern.lstrip('^').rstrip('$')

        # Translate digit classes with quantifiers (e.g., [0-9]{4} -> exactly 4 digits)
        desc = re.sub(r'(\[0-9\]|\\d)\{(\d+)\}', r'exactly \2 digits', desc)
        desc = re.sub(r'(\[0-9\]|\\d)\{(\d+),(\d+)\}', r'\2 to \3 digits', desc)
        desc = re.sub(r'(\[0-9\]|\\d)\+', r'one or more digits', desc)

        # Translate letter classes with quantifiers
        desc = re.sub(r'(\[a-zA-Z\]|\[a-z\]|\[A-Z\]|\\w)\{(\d+)\}', r'exactly \2 letters', desc)
        desc = re.sub(r'(\[a-zA-Z\]|\[a-z\]|\[A-Z\]|\\w)\{(\d+),(\d+)\}', r'\2 to \3 letters', desc)

        # Translate standalone classes
        desc = re.sub(r'\[0-9\]|\\d', 'a digit', desc)
        desc = re.sub(r'\[a-zA-Z\]|\[a-z\]|\[A-Z\]|\\w', 'a letter', desc)

        # Format the final sentence based on string anchors
        if exact_match:
            return f"Must strictly match the format: '{desc}'."
        elif pattern.startswith('^'):
            return f"Must start with: '{desc}'."
        elif pattern.endswith('$'):
            return f"Must end with: '{desc}'."
        else:
            return f"Must contain the pattern: '{desc}'."

    elif rule.type == "range":
        extra = rule.model_extra or {}
        min_val = extra.get('min')
        max_val = extra.get('max')

        if min_val is not None and max_val is not None:
            return f"Value must be between {min_val} and {max_val}."
        elif min_val is not None:
            return f"Value must be at least {min_val}."
        elif max_val is not None:
            return f"Value must be at most {max_val}."
        return "Must be a valid number."

    elif rule.type == "unique":
        return "Value must be unique across the entire dataset."

    elif rule.type == "conditional":
        extra = rule.model_extra or {}
        cond_f = extra.get('condition_field', 'unknown_field')
        cond_v = extra.get('condition_value', 'unknown_value')

        # Dynamically evaluate the target rule to extract its plain English description
        class MockTargetRule:
            def __init__(self, t_type, t_extra):
                self.type = t_type
                self.model_extra = t_extra
                self.description = None

        target_rule = MockTargetRule(extra.get('target_type'), extra)
        target_desc = get_human_readable_description(target_rule)

        if target_desc:
            target_desc = target_desc[0].lower() + target_desc[1:]

        return f"If `{cond_f}` is '{cond_v}', then {target_desc}"

    elif rule.type in ["custom", "transform"]:
        func_path = (rule.model_extra or {}).get('function')
        func_name = func_path.split('.')[-1] if func_path else None

        if func_name and func_name in RULE_REGISTRY:
            doc = RULE_REGISTRY[func_name].__doc__
            if doc:
                return f"*(Custom)* {doc.strip()}"
        return f"Applies custom {rule.type} logic."

    return "Standard validation rule."


class MarkdownRenderer:
    @staticmethod
    def render(validator: DataValidator, profile_name: str) -> str:
        """Generates the legacy Markdown contract for a specific profile."""
        md = [
            f"# Data Quality Contract: `{profile_name}` profile",
            f"*Auto-generated from config version: {validator.version}*\n",
            "---",
            "## 1. Data Shape & Business Rules",
            "| Field | Rule Name | Type | Severity | Description |",
            "|---|---|---|---|---|"
        ]

        for rule in validator.rules:
            field_name = f"`{rule.field}`" if rule.field else "*Cross-field/Dataset*"
            desc = get_human_readable_description(rule).replace("|", "\\|")
            md.append(f"| {field_name} | `{rule.name}` | `{rule.type}` | {rule.severity} | {desc} |")

        md.extend([
            "\n---",
            "## 2. Operational SLAs & Pipeline Thresholds",
            "### Global Settings"
        ])
        global_fail = f"{validator.global_max_fail_pct * 100:.2f}%" if validator.global_max_fail_pct is not None else "Not configured"
        md.extend([
            f"- **Max Batch Failure (Rejection Limit):** {global_fail}",
            f"- **Global Drift Alert (Absolute):** {validator.global_drift_abs_min * 100:.2f}%",
            f"- **Global Drift Alert (Relative):** {validator.global_drift_rel_min * 100:.2f}%\n",
            "### Rule-Specific Thresholds",
            "| Rule Name | Max Fail Limit | Drift Abs Limit | Drift Rel Limit |",
            "|---|---|---|---|"
        ])

        has_sla = False
        for rule in validator.rules:
            if rule.max_fail_pct is not None or rule.drift_abs_min is not None or rule.drift_rel_min is not None:
                has_sla = True
                m_fail = f"{rule.max_fail_pct * 100:.2f}%" if rule.max_fail_pct else "*(Global)*"
                d_abs = f"{rule.drift_abs_min * 100:.2f}%" if rule.drift_abs_min else "*(Global)*"
                d_rel = f"{rule.drift_rel_min * 100:.2f}%" if rule.drift_rel_min else "*(Global)*"
                md.append(f"| `{rule.name}` | {m_fail} | {d_abs} | {d_rel} |")

        if not has_sla:
            md.append("| *(All rules)* | *(Global)* | *(Global)* | *(Global)* |")
        return "\n".join(md)


class HTMLRenderer:
    @staticmethod
    def render(validators: Dict[str, DataValidator]) -> str:
        """Generates a single, zero-dependency HTML dashboard for all profiles."""

        css = """
        :root { --primary: #2563eb; --sidebar: #f8fafc; --text: #334155; --border: #e2e8f0; }
        body { font-family: system-ui, -apple-system, sans-serif; margin: 0; color: var(--text); display: flex; height: 100vh; background: #fff; }
        .sidebar { width: 250px; background: var(--sidebar); border-right: 1px solid var(--border); padding: 1.5rem; overflow-y: auto; }
        .sidebar h2 { font-size: 1.1rem; margin-top: 0; color: #0f172a; text-transform: uppercase; letter-spacing: 0.05em; }
        .nav-btn { display: block; width: 100%; padding: 0.75rem 1rem; margin-bottom: 0.5rem; background: none; border: 1px solid transparent; border-radius: 6px; text-align: left; cursor: pointer; font-size: 0.95rem; color: var(--text); transition: all 0.2s; }
        .nav-btn:hover { background: #e2e8f0; }
        .nav-btn.active { background: #eff6ff; color: var(--primary); border-color: #bfdbfe; font-weight: 600; }
        .content { flex: 1; padding: 2rem 3rem; overflow-y: auto; }
        .profile-section { display: none; }
        .profile-section.active { display: block; }
        h1 { font-size: 1.8rem; color: #0f172a; margin-top: 0; border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; }
        h3 { font-size: 1.2rem; color: #1e293b; margin-top: 2rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.9rem; }
        th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: #f8fafc; font-weight: 600; color: #475569; }
        tr:hover { background: #f8fafc; }
        .badge { padding: 0.25rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
        .badge.ERROR { background: #fee2e2; color: #991b1b; }
        .badge.WARNING { background: #fef3c7; color: #92400e; }
        .badge.INFO { background: #e0f2fe; color: #075985; }
        code { background: #f1f5f9; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; color: #db2777; }
        ul.sla-list { list-style-type: none; padding: 0; }
        ul.sla-list li { padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
        ul.sla-list li strong { color: #0f172a; }
        """

        js = """
        function showProfile(profileName) {
            document.querySelectorAll('.profile-section').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('profile-' + profileName).classList.add('active');
            document.getElementById('btn-' + profileName).classList.add('active');
        }
        """

        html_out = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            f"<head><meta charset='UTF-8'><title>Data Contracts</title><style>{css}</style></head>",
            "<body>",
            "<div class='sidebar'>",
            "<h2>Profiles</h2>"
        ]

        # Generate Sidebar Navigation
        first = True
        for prof_name in validators.keys():
            active_cls = " active" if first else ""
            html_out.append(
                f"<button id='btn-{prof_name}' class='nav-btn{active_cls}' onclick=\"showProfile('{prof_name}')\">{prof_name}</button>")
            first = False
        html_out.append("</div><div class='content'>")

        # Generate Profile Content Sections
        first = True
        for prof_name, validator in validators.items():
            active_cls = " active" if first else ""
            html_out.append(f"<div id='profile-{prof_name}' class='profile-section{active_cls}'>")
            html_out.append(f"<h1>Data Quality Contract: <code>{prof_name}</code></h1>")
            html_out.append(f"<p><strong>Config Version:</strong> {html.escape(str(validator.version))}</p>")

            # Table 1: Business Rules
            html_out.append("<h3>1. Data Shape & Business Rules</h3>")
            html_out.append(
                "<table><thead><tr><th>Field</th><th>Rule Name</th><th>Type</th><th>Severity</th><th>Description</th></tr></thead><tbody>")

            for rule in validator.rules:
                field_name = f"<code>{html.escape(rule.field)}</code>" if rule.field else "<em>Cross-field</em>"
                desc = html.escape(get_human_readable_description(rule))
                badge = f"<span class='badge {rule.severity}'>{rule.severity}</span>"
                html_out.append(
                    f"<tr><td>{field_name}</td><td><code>{html.escape(rule.name)}</code></td><td>{html.escape(rule.type)}</td><td>{badge}</td><td>{desc}</td></tr>")
            html_out.append("</tbody></table>")

            # SLA Sections
            html_out.append("<h3>2. Operational SLAs & Global Thresholds</h3>")
            global_fail = f"{validator.global_max_fail_pct * 100:.2f}%" if validator.global_max_fail_pct is not None else "Not configured"

            html_out.append("<ul class='sla-list'>")
            html_out.append(f"<li><strong>Max Batch Failure (Rejection Limit):</strong> {global_fail}</li>")
            html_out.append(
                f"<li><strong>Global Drift Alert (Absolute):</strong> {validator.global_drift_abs_min * 100:.2f}%</li>")
            html_out.append(
                f"<li><strong>Global Drift Alert (Relative):</strong> {validator.global_drift_rel_min * 100:.2f}%</li>")
            html_out.append("</ul>")

            # Table 2: Rule-Specific SLAs
            html_out.append("<h3>3. Rule-Specific Thresholds</h3>")
            html_out.append(
                "<table><thead><tr><th>Rule Name</th><th>Max Fail Limit</th><th>Drift Abs Limit</th><th>Drift Rel Limit</th></tr></thead><tbody>")

            has_sla = False
            for rule in validator.rules:
                if rule.max_fail_pct is not None or rule.drift_abs_min is not None or rule.drift_rel_min is not None:
                    has_sla = True
                    m_fail = f"{rule.max_fail_pct * 100:.2f}%" if rule.max_fail_pct else "<em>(Global)</em>"
                    d_abs = f"{rule.drift_abs_min * 100:.2f}%" if rule.drift_abs_min else "<em>(Global)</em>"
                    d_rel = f"{rule.drift_rel_min * 100:.2f}%" if rule.drift_rel_min else "<em>(Global)</em>"
                    html_out.append(
                        f"<tr><td><code>{html.escape(rule.name)}</code></td><td>{m_fail}</td><td>{d_abs}</td><td>{d_rel}</td></tr>")

            if not has_sla:
                html_out.append(
                    "<tr><td colspan='4'><em>No rule-specific overrides found. Global limits apply.</em></td></tr>")

            html_out.append("</tbody></table>")
            html_out.append("</div>")  # End profile section
            first = False

        html_out.append("</div>")  # End content
        html_out.append(f"<script>{js}</script></body></html>")

        return "\n".join(html_out)


def main():
    parser = argparse.ArgumentParser(description="Generate Data Quality Contracts from validation configs.")
    # parser.add_argument("--config", type=Path, required=True, help="Path to the YAML config file.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "dev" / "sales_rules.yaml",
                        help="Path to YAML rules")
    parser.add_argument("--output-dir", type=Path, default=Path("docs"), help="Directory to save the files.")
    parser.add_argument("--rules-dir", type=str, default=None, help="Path to the custom rules directory.")
    parser.add_argument("--format", type=str, choices=["markdown", "html", "all"], default="html",
                        help="Output format (markdown, html, or all). Default: html")

    args = parser.parse_args()

    if not args.config.exists():
        logger.error(f"Error: Config file {args.config} not found.")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    profiles = DataValidator.list_profiles(str(args.config))
    if not profiles:
        logger.warning(f"No profiles found in {args.config}.")
        sys.exit(1)

    logger.info(f"Discovered profiles: {', '.join(profiles)}")

    # Pre-load all validators to resolve inheritance trees
    validators = {}
    for profile in profiles:
        try:
            validators[profile] = DataValidator.from_config(str(args.config), profile_name=profile,
                                                            rules_dir=args.rules_dir)
        except Exception as e:
            logger.error(f"Failed to load validator for profile '{profile}': {e}")

    # Generate Markdown
    if args.format in ["markdown", "all"]:
        for profile, validator in validators.items():
            md_content = MarkdownRenderer.render(validator, profile)
            out_file = args.output_dir / f"data_contract_{profile}.md"
            out_file.write_text(md_content, encoding='utf-8')
            logger.info(f"Generated Markdown: {out_file}")

    # Generate HTML
    if args.format in ["html", "all"]:
        html_content = HTMLRenderer.render(validators)
        out_file = args.output_dir / "data_contract_dashboard.html"
        out_file.write_text(html_content, encoding='utf-8')
        logger.info(f"Generated HTML Dashboard: {out_file}")


if __name__ == "__main__":
    main()