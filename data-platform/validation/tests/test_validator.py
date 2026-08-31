import pytest
import pandas as pd
import yaml
from pydantic import ValidationError
from src.validator import ConfigRule, DataValidator


# --- FIXTURES ---

@pytest.fixture
def mock_yaml_config(tmp_path):
    config = {
        "rules": [
            {"name": "req_col", "field": "A", "type": "not_null", "severity": "ERROR"},
            {"name": "range_col", "field": "B", "type": "range", "min": 0, "max": 10, "severity": "WARNING"},
            {"name": "regex_col", "field": "C", "type": "regex", "pattern": "^ID-[0-9]+$", "severity": "ERROR"},
            {"name": "unique_col", "field": "D", "type": "unique", "severity": "INFO"}
        ]
    }
    file_path = tmp_path / "test_rules.yaml"
    with open(file_path, "w") as f:
        yaml.dump(config, f)
    return str(file_path)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "A": [1, pd.NA, 3, 4],
        "B": [5, 15, -1, 5],
        "C": ["ID-1", "ID-2", "BAD", "ID-4"],
        "D": ["x", "y", "z", "x"]
    })


# --- TESTS ---

def test_from_config_loads_correctly(mock_yaml_config):
    validator = DataValidator.from_config(mock_yaml_config)
    assert len(validator.rules) == 4
    assert validator.rules[0].type == "not_null"


def test_from_config_file_not_found():
    with pytest.raises(ValueError, match="Config parse failed"):
        DataValidator.from_config("fake_path/does_not_exist.yaml")


def test_rule_not_null():
    df = pd.DataFrame({"col": ["A", None, "C"]})
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]


def test_rule_range():
    df = pd.DataFrame({"col": [-5, 5, 15, None]})
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "range", "min": 0, "max": 10})
    mask = rule.evaluate(df)
    assert mask.tolist() == [True, False, True, False]


def test_rule_regex():
    df = pd.DataFrame({"col": ["SKU-1234", "BAD-1234", "SKU-9999", None]})
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "regex", "pattern": "^SKU-[0-9]{4}$"})
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False, False]


def test_rule_unique():
    df = pd.DataFrame({"col": ["A", "B", "A", "C", None, None]})
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "unique"})
    mask = rule.evaluate(df)
    assert mask.tolist() == [True, False, True, False, False, False]


def test_missing_column_raises_error():
    """Verifies that an individual rule evaluation throws an error if its target column is missing."""
    df = pd.DataFrame({"other_col": [1, 2]})
    rule = ConfigRule(**{"name": "r1", "field": "missing_col", "type": "not_null"})
    with pytest.raises(ValueError, match="Target field 'missing_col' missing from DataFrame."):
        rule.evaluate(df)


def test_pipeline_missing_columns_fails_fast():
    """Verifies that the entire pipeline halts before processing if configured columns are missing."""
    df = pd.DataFrame({"other_col": [1, 2]})
    validator = DataValidator(
        [ConfigRule(**{"name": "r1", "field": "missing_col", "type": "not_null", "severity": "ERROR"})])

    with pytest.raises(ValueError, match="Missing required columns: missing_col"):
        validator.validate(df)

    with pytest.raises(ValueError, match="Missing required columns: missing_col"):
        validator.clean(df)


def test_severity_error_fails_validation(sample_df, mock_yaml_config):
    validator = DataValidator.from_config(mock_yaml_config)
    report = validator.validate(sample_df)
    assert report['passed'] is False
    assert len(report['errors']) == 2


def test_severity_warning_passes_validation():
    df = pd.DataFrame({"B": [15, 20]})
    validator = DataValidator(
        [ConfigRule(**{"name": "r1", "field": "B", "type": "range", "min": 0, "max": 10, "severity": "WARNING"})])
    report = validator.validate(df)
    assert report['passed'] is True
    assert len(report['warnings']) == 1


def test_empty_dataframe(mock_yaml_config):
    df = pd.DataFrame(columns=["A", "B", "C", "D"])
    validator = DataValidator.from_config(mock_yaml_config)
    report = validator.validate(df)
    assert report['passed'] is False
    assert report['total_rows_affected'] == 0
    assert report['errors'][0]['rule'] == "empty_dataframe"


def test_rule_evaluate_empty_dataframe():
    """Directly hits the df.empty early exit inside ConfigRule.evaluate()."""
    from src.validator import ConfigRule

    # Create an entirely empty dataframe with the required column
    df = pd.DataFrame(columns=["col"])

    # Initialize a standalone rule
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})

    # Evaluate it directly
    mask = rule.evaluate(df)

    # Verify the fallback return statement executed properly
    assert mask.empty is True
    assert mask.dtype == bool

def test_all_null_column():
    df = pd.DataFrame({"A": [None, None]})
    validator = DataValidator([ConfigRule(**{"name": "r1", "field": "A", "type": "not_null", "severity": "ERROR"})])
    report = validator.validate(df)
    assert report['passed'] is False
    assert report['errors'][0]['count'] == 2


def test_mixed_valid_invalid(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config)
    report = validator.validate(sample_df)
    assert report['total_rows_affected'] == 2


def test_sample_bad_rows_formatting(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config)
    report = validator.validate(sample_df)
    sample = report['sample_bad_rows']['regex_col'][0]
    assert sample['row_index'] == 2
    assert sample['failed_value'] == "BAD"
    assert sample['rule_name'] == "regex_col"


def test_clean_strict_true_drops_errors(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config)
    clean_df = validator.clean(sample_df, strict=True)
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 3]


def test_clean_strict_false_drops_specified_rules(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config)
    clean_df = validator.clean(sample_df, strict=False, target_rules=["range_col"])
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 3]


# --- HELPER FUNCTIONS FOR CUSTOM/TRANSFORM RULE TESTS ---

def dummy_custom_rule(df: pd.DataFrame, field: str, target_val: str = 'FAIL', **kwargs) -> pd.Series:
    """A simple dummy function to test the dynamic import engine and kwargs injection."""
    return df[field] == target_val


def dummy_transform_rule(df: pd.DataFrame, target_case: str = 'upper', **kwargs) -> pd.DataFrame:
    """A simple dummy function to test the transform engine and kwargs injection."""
    df_c = df.copy()
    if 'col' in df_c.columns:
        if target_case == 'lower':
            df_c['col'] = df_c['col'].str.lower()
        else:
            df_c['col'] = df_c['col'].str.upper()
    return df_c


def dummy_custom_rule_no_field(df: pd.DataFrame, **kwargs) -> pd.Series:
    """Helper for testing custom rules that evaluate the whole df, lacking a 'field'."""
    return pd.Series([True, False], index=df.index)


def dummy_transform_no_field(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Helper for testing transform rules that don't target a specific field."""
    df_c = df.copy()
    df_c['injected_by_transform'] = True
    return df_c


def crashing_custom_rule(df: pd.DataFrame, **kwargs) -> pd.Series:
    """Helper to simulate a rule that throws an unexpected error."""
    raise ValueError("Simulated crash during evaluation")


def crashing_transform_rule(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Helper to simulate a transform that throws an unexpected error."""
    raise ValueError("Simulated crash during transformation")


# --- ENGINE TESTS ---

def test_rule_custom():
    df = pd.DataFrame({"col": ["PASS", "FAIL", "PASS"]})
    rule = ConfigRule(**{
        "name": "r1",
        "field": "col",
        "type": "custom",
        "function": "tests.test_validator.dummy_custom_rule"
    })
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]


def test_custom_rule_with_kwargs():
    df = pd.DataFrame({"col": ["PASS", "TARGET", "PASS"]})
    rule = ConfigRule(**{
        "name": "r1",
        "field": "col",
        "type": "custom",
        "function": "tests.test_validator.dummy_custom_rule",
        "target_val": "TARGET"
    })
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]


def test_custom_rule_missing_function():
    df = pd.DataFrame({"col": ["PASS"]})
    rule = ConfigRule(**{"name": "bad_rule", "field": "col", "type": "custom"})
    with pytest.raises(ValueError, match="missing 'function' path"):
        rule.evaluate(df)


def test_custom_rule_bad_import():
    df = pd.DataFrame({"col": ["PASS"]})
    rule = ConfigRule(**{
        "name": "bad_rule",
        "field": "col",
        "type": "custom",
        "function": "fake_module.fake_function"
    })
    with pytest.raises(RuntimeError, match="Failed to load function"):
        rule.evaluate(df)


def test_rule_transform_evaluation():
    df = pd.DataFrame({"col": ["pass", "pass"]})
    rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "dummy",
        "severity": "INFO"
    })
    mask = rule.evaluate(df)
    assert mask.all() == False


def test_transform_rule_with_kwargs():
    df = pd.DataFrame({"col": ["MixedCase"]})
    rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "tests.test_validator.dummy_transform_rule",
        "target_case": "lower",
        "severity": "INFO"
    })
    clean_df = rule.apply_transform(df)
    assert clean_df.at[0, "col"] == "mixedcase"


def test_transform_rule_missing_function():
    df = pd.DataFrame({"col": ["pass"]})
    rule = ConfigRule(**{"name": "bad_transform", "type": "transform"})
    with pytest.raises(ValueError, match="missing 'function' path"):
        rule.apply_transform(df)


def test_transform_rule_bad_import():
    df = pd.DataFrame({"col": ["pass"]})
    rule = ConfigRule(**{
        "name": "bad_transform",
        "type": "transform",
        "function": "fake_module.fake_function"
    })
    with pytest.raises(RuntimeError, match="Failed to load function"):
        rule.apply_transform(df)


def test_apply_transform_fallback():
    df = pd.DataFrame({"A": [1, 2]})
    rule = ConfigRule(**{"name": "r1", "field": "A", "type": "not_null"})
    out_df = rule.apply_transform(df)
    assert out_df.equals(df)


def test_clean_applies_transforms():
    df = pd.DataFrame({
        "req_col": [1, None, 3],
        "col": ["lower", "drop_me", "mixedCase"]
    })
    r1 = ConfigRule(**{"name": "r1", "field": "req_col", "type": "not_null", "severity": "ERROR"})
    r2 = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "tests.test_validator.dummy_transform_rule",
        "severity": "INFO"
    })

    validator = DataValidator([r1, r2])
    clean_df = validator.clean(df, strict=True)
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 2]
    assert clean_df.at[0, "col"] == "LOWER"
    assert clean_df.at[2, "col"] == "MIXEDCASE"


# --- 100% COVERAGE EDGE CASE TESTS ---

def test_from_config_yaml_error(tmp_path):
    bad_yaml = tmp_path / "bad_syntax.yaml"
    with open(bad_yaml, "w") as f:
        f.write("] : invalid : yaml : [")

    with pytest.raises(ValueError, match="Config parse failed"):
        DataValidator.from_config(str(bad_yaml))


def test_from_config_validation_error(tmp_path):
    bad_schema = tmp_path / "bad_schema.yaml"
    with open(bad_schema, "w") as f:
        yaml.dump({"rules": [{"name": "r1", "type": "not_null", "severity": "SUPER_ERROR"}]}, f)

    with pytest.raises(ValidationError):
        DataValidator.from_config(str(bad_schema))


def test_evaluate_unknown_rule_type():
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{"name": "r1", "field": "A", "type": "not_null"})

    rule.type = "magic"  # type: ignore

    with pytest.raises(ValueError, match="Unknown rule type: magic"):
        rule.evaluate(df)


def test_regex_rule_missing_pattern():
    df = pd.DataFrame({"A": ["test"]})
    rule = ConfigRule(**{"name": "missing_pattern_rule", "field": "A", "type": "regex"})

    with pytest.raises(ValueError, match="Regex missing 'pattern'"):
        rule.evaluate(df)


def test_uppercase_severity_non_string():
    with pytest.raises(ValidationError):
        ConfigRule(**{"name": "r1", "type": "not_null", "severity": 123})


def test_missing_field_for_field_bound_rule():
    with pytest.raises(ValidationError, match="requires a 'field' to be specified"):
        ConfigRule(**{"name": "bad_rule", "type": "not_null", "severity": "ERROR"})


def test_validation_result_dict_access():
    """Hits ValidationResult.__getitem__ and verifies attribute/dict parity."""
    from src.validator import ValidationResult
    res = ValidationResult(passed=True, total_rows_affected=10)

    assert res["passed"] is True
    assert res["total_rows_affected"] == 10

    with pytest.raises(KeyError):
        _ = res["does_not_exist"]


def test_from_config_empty_or_missing_rules(tmp_path):
    """Hits data.get('rules', []) fallback and verifies 'YAML file is completely empty' exception."""
    from src.validator import DataValidator

    # 1. Valid YAML structure without 'rules' key
    no_rules = tmp_path / "no_rules.yaml"
    no_rules.write_text("some_other_key: value")
    val1 = DataValidator.from_config(str(no_rules))
    assert len(val1.rules) == 0

    # 2. Completely empty YAML file (triggers `if data is None: raise ValueError("YAML file is completely empty.")`)
    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("")
    with pytest.raises(ValueError, match="YAML file is completely empty"):
        DataValidator.from_config(str(empty_yaml))


def test_evaluate_and_transform_without_field():
    """Hits branches in evaluate(), apply_transform(), and validate() where rule.field is None."""
    from src.validator import ConfigRule, DataValidator
    df = pd.DataFrame({"A": [1, 2]})

    rule_custom = ConfigRule(**{
        "name": "custom_no_field",
        "type": "custom",
        "severity": "ERROR",
        "function": "tests.test_validator.dummy_custom_rule_no_field"
    })

    rule_transform = ConfigRule(**{
        "name": "transform_no_field",
        "type": "transform",
        "severity": "INFO",
        "function": "tests.test_validator.dummy_transform_no_field"
    })

    validator = DataValidator([rule_custom, rule_transform])

    report = validator.validate(df)
    assert report.passed is False
    assert report.sample_bad_rows['custom_no_field'][0]['failed_value'] is None

    clean_df = validator.clean(df)
    assert "injected_by_transform" in clean_df.columns


def test_failsafe_validate_skips_crashing_rule(caplog):
    """Hits the except Exception block in validator.validate()."""
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{
        "name": "crash_eval",
        "type": "custom",
        "severity": "ERROR",
        "function": "tests.test_validator.crashing_custom_rule"
    })
    validator = DataValidator([rule])

    report = validator.validate(df)

    assert report.passed is True
    assert "FATAL ERROR: Rule 'crash_eval' crashed during validation" in caplog.text


def test_failsafe_clean_skips_crashing_rules(caplog):
    """Hits the except Exception blocks in validator.clean() for both evaluation and transforms."""
    df = pd.DataFrame({"A": [1]})
    r1 = ConfigRule(**{
        "name": "crash_eval",
        "type": "custom",
        "severity": "ERROR",
        "function": "tests.test_validator.crashing_custom_rule"
    })
    r2 = ConfigRule(**{
        "name": "crash_transform",
        "type": "transform",
        "severity": "INFO",
        "function": "tests.test_validator.crashing_transform_rule"
    })

    validator = DataValidator([r1, r2])
    clean_df = validator.clean(df, strict=True)

    assert len(clean_df) == 1
    assert "FATAL ERROR: Transform rule 'crash_transform' crashed" in caplog.text
    assert "FATAL ERROR: Rule 'crash_eval' crashed during cleaning" in caplog.text

# --- RECENT FEATURE TESTS (Dependencies & Transforms) ---

def test_validation_result_config_version():
    """Verifies that the new config_version attribute is available and defaults to 'unknown'."""
    from src.validator import ValidationResult
    res = ValidationResult(passed=True, total_rows_affected=0)
    assert res.config_version == 'unknown'


def test_rule_dependencies_suppression():
    """Proves that a rule correctly suppresses failures if a dependency already flagged the row."""
    # Row 0: Null, Row 1: 150 (Out of bounds), Row 2: 50 (Valid)
    df = pd.DataFrame({"qty": [pd.NA, 150, 50]})

    rule_a = ConfigRule(**{
        "name": "rule_a",
        "field": "qty",
        "type": "not_null",
        "severity": "ERROR"
    })

    # Range rule mathematically fails on Nulls too, but we want to explicitly
    # suppress it because rule_a already caught it.
    rule_b = ConfigRule(**{
        "name": "rule_b",
        "field": "qty",
        "type": "range",
        "min": 0,
        "max": 100,
        "severity": "WARNING",
        "depends_on": ["rule_a"]
    })

    validator = DataValidator([rule_a, rule_b])

    # 1. Test validation reporting suppression
    report = validator.validate(df)
    err_counts = {err['rule']: err['count'] for err in report.errors}
    warn_counts = {warn['rule']: warn['count'] for warn in report.warnings}

    assert err_counts.get("rule_a") == 1  # Flags Row 0
    assert warn_counts.get("rule_b") == 1  # Flags Row 1 ONLY (Row 0 is suppressed)

    # 2. Test strict cleaning suppression
    # We set strict=False but target both rules to see what indices get dropped
    clean_df = validator.clean(df, strict=False, target_rules=["rule_a", "rule_b"])

    # Row 0 and Row 1 should be dropped. Row 2 remains.
    assert len(clean_df) == 1
    assert clean_df.index[0] == 2


def test_rule_dependency_not_found_logs_warning(caplog):
    """Hits the branch where a rule depends on a rule that hasn't executed/doesn't exist."""
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{
        "name": "rule_b",
        "field": "A",
        "type": "not_null",
        "depends_on": ["missing_rule"]
    })
    validator = DataValidator([rule])

    # Hits the warning branch in validate()
    validator.validate(df)
    assert "Dependency 'missing_rule' for rule 'rule_b' not found or not executed yet." in caplog.text

    # Hits the warning branch in clean()
    caplog.clear()
    validator.clean(df)
    assert "Dependency 'missing_rule' for rule 'rule_b' not found/executed." in caplog.text


def test_validate_evaluates_transformed_working_copy():
    """Proves that validate() runs rules against the df_working copy, not raw df."""
    df = pd.DataFrame({"col": ["mixedCase"]})

    # Transform makes the string lowercase -> "mixedcase"
    t_rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "tests.test_validator.dummy_transform_rule",
        "target_case": "lower",
        "severity": "INFO"
    })

    # Regex explicitly expects lowercase only.
    # If evaluate() runs on the raw df, it fails. If it runs on df_working, it passes.
    v_rule = ConfigRule(**{
        "name": "v1",
        "field": "col",
        "type": "regex",
        "pattern": "^[a-z]+$",
        "severity": "ERROR"
    })

    validator = DataValidator([t_rule, v_rule])
    report = validator.validate(df)

    # Assert validation passes because the regex evaluated the transformed lowercase data
    assert report.passed is True


def test_failsafe_validate_skips_crashing_transform_setup(caplog):
    """Hits the exception block for the transform pre-pass inside validate()."""
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{
        "name": "crash_setup",
        "type": "transform",
        "severity": "INFO",
        "function": "tests.test_validator.crashing_transform_rule"
    })

    validator = DataValidator([rule])
    report = validator.validate(df)

    assert report.passed is True
    assert "FATAL ERROR: Transform 'crash_setup' crashed during validation setup" in caplog.text