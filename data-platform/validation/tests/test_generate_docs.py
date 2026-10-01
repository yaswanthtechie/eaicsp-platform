import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

# Add project root to path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.registry import clear_registry, discover_rules


@pytest.fixture(autouse=True)
def setup_dynamic_registry():
    """Cleans registry state and loads rules before and after each test."""
    clear_registry()
    discover_rules(PROJECT_ROOT / "rules")
    yield
    clear_registry()


from src.validator import ConfigRule
from src.generate_docs import get_human_readable_description, MarkdownRenderer, HTMLRenderer, main


# ==========================================
# TEST: get_human_readable_description
# ==========================================

def test_get_description_explicit_yaml():
    rule = ConfigRule(name="test", type="not_null", field="f1", description="Custom explicit description.")
    assert get_human_readable_description(rule) == "Custom explicit description."


def test_get_description_not_null():
    rule = ConfigRule(name="test", type="not_null", field="f1")
    assert get_human_readable_description(rule) == "Must not be empty or null."


def test_get_description_regex():
    """Tests the new dynamic regex-to-plain-English parser."""
    # 1. Exact match basic
    rule = ConfigRule(name="test", type="regex", field="f1", pattern="^ABC$")
    assert get_human_readable_description(rule) == "Must strictly match the format: 'ABC'."

    # 2. Unknown fallback
    rule_no_pattern = ConfigRule(name="test", type="regex", field="f1")
    assert get_human_readable_description(rule_no_pattern) == "Must match a specific format."

    # 3. Dynamic digit class parsing
    rule_sku = ConfigRule(name="test", type="regex", field="f1", pattern="^SKU-[0-9]{4}$")
    assert get_human_readable_description(rule_sku) == "Must strictly match the format: 'SKU-exactly 4 digits'."

    # 4. Starts with anchor
    rule_start = ConfigRule(name="test", type="regex", field="f1", pattern="^PREFIX-")
    assert get_human_readable_description(rule_start) == "Must start with: 'PREFIX-'."

    # 5. Ends with anchor
    rule_end = ConfigRule(name="test", type="regex", field="f1", pattern="-SUFFIX$")
    assert get_human_readable_description(rule_end) == "Must end with: '-SUFFIX'."

    # 6. Contains pattern (No anchors) and letter classes
    rule_contain = ConfigRule(name="test", type="regex", field="f1", pattern="[a-zA-Z]{2,4}")
    assert get_human_readable_description(rule_contain) == "Must contain the pattern: '2 to 4 letters'."

    # 7. Plus quantifier
    rule_plus = ConfigRule(name="test", type="regex", field="f1", pattern="\\d+")
    assert get_human_readable_description(rule_plus) == "Must contain the pattern: 'one or more digits'."


def test_get_description_range():
    """Tests the new open-ended range plain English generator."""
    rule_both = ConfigRule(name="test", type="range", field="f1", min=10, max=100)
    assert get_human_readable_description(rule_both) == "Value must be between 10 and 100."

    rule_min_only = ConfigRule(name="test", type="range", field="f1", min=10)
    assert get_human_readable_description(rule_min_only) == "Value must be at least 10."

    rule_max_only = ConfigRule(name="test", type="range", field="f1", max=100)
    assert get_human_readable_description(rule_max_only) == "Value must be at most 100."

    rule_no_bounds = ConfigRule(name="test", type="range", field="f1")
    assert get_human_readable_description(rule_no_bounds) == "Must be a valid number."


def test_get_description_unique():
    rule = ConfigRule(name="test", type="unique", field="f1")
    assert get_human_readable_description(rule) == "Value must be unique across the entire dataset."


def test_get_description_conditional():
    """Tests the dynamic recursive unwrapping of conditional targets."""
    rule = ConfigRule(
        name="test", type="conditional", condition_field="country",
        condition_value="US", target_type="not_null"
    )
    assert get_human_readable_description(rule) == "If country is 'US', then must not be empty or null."

    # Test with a missing/unknown target type to ensure lowercase formatting handles it safely
    rule_unknown = ConfigRule(
        name="test", type="conditional", condition_field="country",
        condition_value="US", target_type="unknown_type"
    )
    assert get_human_readable_description(rule_unknown) == "If country is 'US', then standard validation rule."


def test_get_description_custom_with_docstring():
    rule = ConfigRule(name="test", type="custom", function="check_unparseable_dates")
    desc = get_human_readable_description(rule)
    assert desc.startswith("(Custom) ")
    assert "Flags dates that failed standard parsing" in desc


def test_get_description_transform():
    rule = ConfigRule(name="test", type="transform", function="standardize_products")
    desc = get_human_readable_description(rule)
    assert desc.startswith("(Custom) ")
    assert "Cleans text columns" in desc


def test_get_description_custom_no_docstring_or_unknown():
    mock_rule = MagicMock()
    mock_rule.description = None
    mock_rule.type = "custom"
    mock_rule.model_extra = {"function": "non_existent_function"}
    assert get_human_readable_description(mock_rule) == "Applies custom custom logic."


def test_get_description_unknown_type():
    mock_rule = MagicMock()
    mock_rule.description = None
    mock_rule.type = "bizarre_rule_type"
    assert get_human_readable_description(mock_rule) == "Standard validation rule."


# ==========================================
# TEST: MarkdownRenderer
# ==========================================

def test_markdown_renderer():
    mock_validator = MagicMock()
    mock_validator.version = "1.0.0"
    mock_validator.global_max_fail_pct = 0.25
    mock_validator.global_drift_abs_min = 0.01
    mock_validator.global_drift_rel_min = 0.50
    mock_validator.global_warning_fail_pct = None
    mock_validator.global_max_duration_seconds = None

    rule_with_sla = ConfigRule(
        name="rule_1", type="not_null", field="f1", severity="ERROR",
        max_fail_pct=0.05, drift_abs_min=0.02
    )

    rule_without_sla = ConfigRule(
        name="rule_2", type="custom", function="check_composite_unique", severity="WARNING"
    )

    mock_validator.rules = [rule_with_sla, rule_without_sla]
    markdown = MarkdownRenderer.render(mock_validator, "default")

    assert "# Data Quality Contract: `default` profile" in markdown
    assert "1.0.0" in markdown
    assert "`rule_1`" in markdown
    assert "25.00%" in markdown
    assert "*(Global)*" in markdown


def test_markdown_renderer_no_sla_rules():
    mock_validator = MagicMock()
    mock_validator.version = "1.0"
    mock_validator.global_max_fail_pct = None
    mock_validator.global_drift_abs_min = 0.0
    mock_validator.global_drift_rel_min = 0.0
    mock_validator.global_warning_fail_pct = None
    mock_validator.global_max_duration_seconds = None
    mock_validator.rules = [ConfigRule(name="rule_1", type="not_null", field="f1")]

    markdown = MarkdownRenderer.render(mock_validator, "strict")
    assert "| *(All rules)* | *(Global)* | *(Global)* | *(Global)* |" in markdown
    assert "Not configured" in markdown


# ==========================================
# TEST: HTMLRenderer
# ==========================================

def test_html_renderer_with_slas():
    mock_validator = MagicMock()
    mock_validator.version = "1.0.0"
    mock_validator.global_max_fail_pct = 0.20
    mock_validator.global_drift_abs_min = 0.01
    mock_validator.global_drift_rel_min = 0.50
    mock_validator.global_warning_fail_pct = 0.10
    mock_validator.global_max_duration_seconds = 5.0

    rule = ConfigRule(name="rule_1", type="not_null", field="f1", severity="ERROR", max_fail_pct=0.05)
    mock_validator.rules = [rule]

    html = HTMLRenderer.render({"default": mock_validator})

    assert "<!DOCTYPE html>" in html
    assert "Data Quality Contract: <code>default</code>" in html
    assert "20.00%" in html
    assert "5.00%" in html
    assert "<em>(Global)</em>" in html
    assert "Send an SLA warning if more than this share of rows fail:</strong> 10.00%" in html
    assert "Send an SLA warning if validation takes longer than:</strong> 5 seconds" in html


def test_html_renderer_escapes_profile_names():
    mock_validator = MagicMock()
    mock_validator.version = "1.0.0"
    mock_validator.global_max_fail_pct = 0.0          # 0% is a real setting, not "Not configured"
    mock_validator.global_drift_abs_min = 0.0
    mock_validator.global_drift_rel_min = 0.0
    mock_validator.global_warning_fail_pct = None
    mock_validator.global_max_duration_seconds = None
    mock_validator.rules = [ConfigRule(name="rule_1", type="not_null", field="f1", max_fail_pct=0.0)]

    html = HTMLRenderer.render({"<script>alert(1)</script>": mock_validator})

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "0.00%" in html


def test_html_renderer_no_slas():
    mock_validator = MagicMock()
    mock_validator.version = "1.0.0"
    mock_validator.global_max_fail_pct = None
    mock_validator.global_drift_abs_min = 0.0
    mock_validator.global_drift_rel_min = 0.0
    mock_validator.global_warning_fail_pct = None
    mock_validator.global_max_duration_seconds = None

    rule = ConfigRule(name="rule_1", type="not_null", field="f1", severity="WARNING")
    mock_validator.rules = [rule]

    html = HTMLRenderer.render({"strict": mock_validator})

    assert "Not configured" in html
    assert "No rule-specific overrides found. Global limits apply." in html


# ==========================================
# TEST: main() CLI execution
# ==========================================

@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
def test_main_config_not_found(mock_exists, mock_parse_args):
    mock_args = MagicMock()
    mock_args.config = Path("non_existent.yaml")
    mock_parse_args.return_value = mock_args
    mock_exists.return_value = False

    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1


@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
@patch("src.validator.DataValidator.list_profiles")
def test_main_no_profiles_found(mock_list, mock_exists, mock_parse_args):
    mock_args = MagicMock()
    mock_args.config = Path("config.yaml")
    mock_parse_args.return_value = mock_args
    mock_exists.return_value = True
    mock_list.return_value = []

    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1


@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("src.validator.DataValidator.list_profiles")
@patch("src.validator.DataValidator.from_config")
@patch("pathlib.Path.write_text")
def test_main_success_all_formats(mock_write_text, mock_from_config, mock_list, mock_mkdir, mock_exists,
                                  mock_parse_args):
    mock_args = MagicMock()
    mock_args.config = Path("config.yaml")
    mock_args.output_dir = Path("docs")
    mock_args.format = "all"
    mock_parse_args.return_value = mock_args

    mock_exists.return_value = True
    mock_list.return_value = ["default", "strict"]

    mock_validator = MagicMock()
    mock_validator.rules = []
    mock_validator.version = "1.0"
    mock_validator.global_max_fail_pct = 0.1
    mock_validator.global_drift_abs_min = 0.1
    mock_validator.global_drift_rel_min = 0.1
    mock_validator.global_warning_fail_pct = None
    mock_validator.global_max_duration_seconds = None
    mock_from_config.return_value = mock_validator

    main()

    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    assert mock_from_config.call_count == 2
    # 2 profiles for markdown + 1 combined HTML file = 3 writes
    assert mock_write_text.call_count == 3


@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("src.validator.DataValidator.list_profiles")
@patch("src.validator.DataValidator.from_config")
def test_main_exception_during_generation(mock_from_config, mock_list, mock_mkdir, mock_exists, mock_parse_args,
                                          caplog):
    mock_args = MagicMock()
    mock_args.config = Path("config.yaml")
    mock_args.format = "html"
    mock_parse_args.return_value = mock_args

    mock_exists.return_value = True
    mock_list.return_value = ["default"]

    mock_from_config.side_effect = Exception("YAML Parsing Error")

    main()

    assert "Failed to load validator for profile 'default': YAML Parsing Error" in caplog.text