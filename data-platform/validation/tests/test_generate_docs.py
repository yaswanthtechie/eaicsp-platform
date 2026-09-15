import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

# Add project root to path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the modules we are testing
from src.validator import ConfigRule
from src.generate_docs import get_human_readable_description, generate_markdown_for_profile, main


# ==========================================
# TEST: get_human_readable_description
# ==========================================

def test_get_description_explicit_yaml():
    """Test that explicit descriptions in YAML override everything else."""
    rule = ConfigRule(name="test", type="not_null", field="f1", description="Custom explicit description.")
    assert get_human_readable_description(rule) == "Custom explicit description."


def test_get_description_not_null():
    rule = ConfigRule(name="test", type="not_null", field="f1")
    assert get_human_readable_description(rule) == "Must not be empty or null."


def test_get_description_regex():
    rule = ConfigRule(name="test", type="regex", field="f1", pattern="^ABC$")
    assert get_human_readable_description(rule) == "Must strictly match the regex pattern: `^ABC$`"

    # Test missing pattern fallback
    rule_no_pattern = ConfigRule(name="test", type="regex", field="f1")
    assert get_human_readable_description(rule_no_pattern) == "Must strictly match the regex pattern: `unknown`"


def test_get_description_range():
    rule = ConfigRule(name="test", type="range", field="f1", min=10, max=100)
    assert get_human_readable_description(rule) == "Value must be between **10** and **100**."

    # Test missing bounds fallback
    rule_no_bounds = ConfigRule(name="test", type="range", field="f1")
    assert get_human_readable_description(rule_no_bounds) == "Value must be between **-∞** and **∞**."


def test_get_description_unique():
    rule = ConfigRule(name="test", type="unique", field="f1")
    assert get_human_readable_description(rule) == "Value must be unique across the entire dataset."


def test_get_description_conditional():
    rule = ConfigRule(
        name="test",
        type="conditional",
        condition_field="country",
        condition_value="US",
        target_type="not_null"  # Required by validator conditional schema
    )
    assert get_human_readable_description(rule) == "If `country` == 'US', secondary validation rules apply."


def test_get_description_custom_with_docstring():
    rule = ConfigRule(
        name="test",
        type="custom",
        function="src.custom_rules.check_unparseable_dates"
    )
    # This should pull the actual docstring from your custom_rules.py
    desc = get_human_readable_description(rule)
    assert "*(Custom)*" in desc
    assert "Flags dates that failed standard parsing" in desc


def test_get_description_custom_no_docstring_or_unknown():
    # Use MagicMock to bypass Pydantic's SecurityError for unregistered functions
    mock_rule = MagicMock()
    mock_rule.description = None
    mock_rule.type = "custom"
    mock_rule.model_extra = {"function": "src.custom_rules.non_existent_function"}

    assert get_human_readable_description(mock_rule) == "Applies custom custom logic."


def test_get_description_unknown_type():
    # Force an unknown type by bypassing Pydantic validation via dictionary mocking
    mock_rule = MagicMock()
    mock_rule.description = None
    mock_rule.type = "bizarre_rule_type"
    assert get_human_readable_description(mock_rule) == "Standard validation rule."


# ==========================================
# TEST: generate_markdown_for_profile
# ==========================================

def test_generate_markdown_for_profile():
    # Setup mock validator and rules
    mock_validator = MagicMock()
    mock_validator.version = "1.0.0"
    mock_validator.global_max_fail_pct = 0.25
    mock_validator.global_drift_abs_min = 0.01
    mock_validator.global_drift_rel_min = 0.50

    # Omit drift_rel_min so it triggers the *(Global)* fallback string in the table
    rule_with_sla = ConfigRule(
        name="rule_1", type="not_null", field="f1", severity="ERROR",
        max_fail_pct=0.05, drift_abs_min=0.02
    )

    rule_without_sla = ConfigRule(
        name="rule_2",
        type="custom",
        function="src.custom_rules.check_composite_unique",
        severity="WARNING"
    )

    mock_validator.rules = [rule_with_sla, rule_without_sla]

    markdown = generate_markdown_for_profile(mock_validator, "default")

    # Assertions for Section 1: Business Rules
    assert "# Data Quality Contract: `default` profile" in markdown
    assert "1.0.0" in markdown
    assert "`rule_1`" in markdown
    assert "`not_null`" in markdown
    assert "*Cross-field/Dataset*" in markdown  # Testing the null-field fallback

    # Assertions for Section 2: SLAs
    assert "25.00%" in markdown  # 0.25 max fail pct formatted
    assert "1.00%" in markdown  # 0.01 abs min formatted
    assert "50.00%" in markdown  # 0.50 rel min formatted
    assert "5.00%" in markdown  # rule_1 max_fail_pct
    assert "2.00%" in markdown  # rule_1 drift abs
    assert "*(Global)*" in markdown  # rule_1 falling back to global for drift_rel_min


def test_generate_markdown_no_sla_rules():
    mock_validator = MagicMock()
    mock_validator.version = "1.0"
    mock_validator.global_max_fail_pct = None
    mock_validator.global_drift_abs_min = 0.0
    mock_validator.global_drift_rel_min = 0.0

    # Rule with NO SLAs
    mock_validator.rules = [ConfigRule(name="rule_1", type="not_null", field="f1")]

    markdown = generate_markdown_for_profile(mock_validator, "strict")
    assert "| *(All rules)* | *(Global)* | *(Global)* | *(Global)* |" in markdown
    assert "Not configured" in markdown  # Global max fail is None


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
    mock_list.return_value = []  # Return empty list

    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1


@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("src.validator.DataValidator.list_profiles")
@patch("src.validator.DataValidator.from_config")
@patch("builtins.open", new_callable=mock_open)
def test_main_success(mock_file, mock_from_config, mock_list, mock_mkdir, mock_exists, mock_parse_args):
    mock_args = MagicMock()
    mock_args.config = Path("config.yaml")
    mock_args.output_dir = Path("docs")
    mock_parse_args.return_value = mock_args

    mock_exists.return_value = True
    mock_list.return_value = ["default", "strict"]

    mock_validator = MagicMock()
    mock_validator.rules = []
    mock_validator.version = "1.0"
    mock_validator.global_max_fail_pct = 0.1
    mock_validator.global_drift_abs_min = 0.1
    mock_validator.global_drift_rel_min = 0.1
    mock_from_config.return_value = mock_validator

    main()

    # Ensure directory creation was called
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    # Ensure it iterated through both profiles
    assert mock_from_config.call_count == 2
    # Ensure files were opened and written to
    assert mock_file.call_count == 2


@patch("argparse.ArgumentParser.parse_args")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.mkdir")
@patch("src.validator.DataValidator.list_profiles")
@patch("src.validator.DataValidator.from_config")
def test_main_exception_during_generation(mock_from_config, mock_list, mock_mkdir, mock_exists, mock_parse_args,
                                          caplog):
    mock_args = MagicMock()
    mock_args.config = Path("config.yaml")
    mock_parse_args.return_value = mock_args

    mock_exists.return_value = True
    mock_list.return_value = ["default"]

    # Simulate a crash when trying to load the profile (e.g. invalid YAML)
    mock_from_config.side_effect = Exception("YAML Parsing Error")

    # Execute main. It catches exceptions internally and logs an error, so it shouldn't sys.exit()
    main()

    assert "Failed to generate docs for profile 'default': YAML Parsing Error" in caplog.text