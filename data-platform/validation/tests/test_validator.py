import pytest
import pandas as pd
import yaml
from pydantic import ValidationError
from src.validator import ConfigRule, DataValidator, ValidationResult, SecurityError
from src.registry import RULE_REGISTRY, clear_registry, register_rule
import rules.custom_rules as real_custom_rules


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

def dummy_check_composite_unique(df: pd.DataFrame, **kwargs) -> pd.Series:
    """Mock for Pass 1 streaming tests."""
    return pd.Series([False] * len(df), index=df.index)

def dummy_check_composite_unique_stream(df: pd.DataFrame, **kwargs) -> pd.Series:
    """Mock for Pass 2 streaming tests to read injected state."""
    return df.get('_global_dup_mask', pd.Series([False] * len(df), index=df.index))


@pytest.fixture(autouse=True)
def inject_test_registry_functions():
    """
    Runs before every test in this file.
    Injects dummy functions directly into the dynamic registry.
    """
    clear_registry()
    RULE_REGISTRY.update({
        "dummy_custom_rule": dummy_custom_rule,
        "dummy_transform_rule": dummy_transform_rule,
        "dummy_custom_rule_no_field": dummy_custom_rule_no_field,
        "dummy_transform_no_field": dummy_transform_no_field,
        "crashing_custom_rule": crashing_custom_rule,
        "crashing_transform_rule": crashing_transform_rule,
        "check_composite_unique": dummy_check_composite_unique,
        "check_composite_unique_stream": dummy_check_composite_unique_stream,
    })
    yield
    clear_registry()


# --- TESTS ---

def test_from_config_loads_correctly(mock_yaml_config):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    assert len(validator.rules) == 4
    assert validator.rules[0].type == "not_null"

def test_from_config_file_not_found():
    with pytest.raises(ValueError, match="Config parse failed"):
        DataValidator.from_config("fake_path/does_not_exist.yaml", rules_dir="dummy")

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
    df = pd.DataFrame({"other_col": [1, 2]})
    rule = ConfigRule(**{"name": "r1", "field": "missing_col", "type": "not_null"})
    with pytest.raises(ValueError, match="Target field 'missing_col' missing from DataFrame."):
        rule.evaluate(df)

def test_pipeline_missing_columns_fails_fast():
    df = pd.DataFrame({"other_col": [1, 2]})
    validator = DataValidator(
        [ConfigRule(**{"name": "r1", "field": "missing_col", "type": "not_null", "severity": "ERROR"})])
    with pytest.raises(ValueError, match="Missing required columns: missing_col"):
        validator.validate(df)
    with pytest.raises(ValueError, match="Missing required columns: missing_col"):
        validator.clean(df)

def test_severity_error_fails_validation(sample_df, mock_yaml_config):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
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
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    report = validator.validate(df)
    assert report['passed'] is False
    assert report['total_rows_affected'] == 0
    assert report['errors'][0]['rule'] == "empty_dataframe"

def test_rule_evaluate_empty_dataframe():
    df = pd.DataFrame(columns=["col"])
    rule = ConfigRule(**{"name": "r1", "field": "col", "type": "not_null"})
    mask = rule.evaluate(df)
    assert mask.empty is True
    assert mask.dtype == bool

def test_all_null_column():
    df = pd.DataFrame({"A": [None, None]})
    validator = DataValidator([ConfigRule(**{"name": "r1", "field": "A", "type": "not_null", "severity": "ERROR"})])
    report = validator.validate(df)
    assert report['passed'] is False
    assert report['errors'][0]['count'] == 2

def test_mixed_valid_invalid(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    report = validator.validate(sample_df)
    assert report['total_rows_affected'] == 2

def test_sample_bad_rows_formatting(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    report = validator.validate(sample_df)
    sample = report['sample_bad_rows']['regex_col'][0]
    assert sample['row_index'] == 2
    assert sample['failed_value'] == "BAD"
    assert sample['rule_name'] == "regex_col"

def test_clean_strict_true_drops_errors(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    clean_df = validator.clean(sample_df, strict=True)
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 3]

def test_clean_strict_false_drops_specified_rules(mock_yaml_config, sample_df):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    clean_df = validator.clean(sample_df, strict=False, target_rules=["range_col"])
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 3]


# --- ENGINE TESTS ---

def test_rule_custom():
    df = pd.DataFrame({"col": ["PASS", "FAIL", "PASS"]})
    rule = ConfigRule(**{
        "name": "r1",
        "field": "col",
        "type": "custom",
        "function": "dummy_custom_rule"
    })
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]

def test_custom_rule_with_kwargs():
    df = pd.DataFrame({"col": ["PASS", "TARGET", "PASS"]})
    rule = ConfigRule(**{
        "name": "r1",
        "field": "col",
        "type": "custom",
        "function": "dummy_custom_rule",
        "target_val": "TARGET"
    })
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]

def test_custom_rule_missing_function():
    with pytest.raises(ValidationError, match="no 'function' path"):
        ConfigRule(**{"name": "bad_rule", "field": "col", "type": "custom"})

def test_custom_rule_bad_import():
    with pytest.raises(SecurityError, match="not in the active registry"):
        ConfigRule(**{
            "name": "bad_rule",
            "field": "col",
            "type": "custom",
            "function": "fake_module.fake_function"
        })

def test_rule_transform_evaluation():
    RULE_REGISTRY["dummy_transform"] = lambda df: pd.Series([False, False])
    df = pd.DataFrame({"col": ["pass", "pass"]})
    rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "dummy_transform",
        "severity": "INFO"
    })
    mask = rule.evaluate(df)
    assert mask.all() == False

def test_transform_rule_with_kwargs():
    df = pd.DataFrame({"col": ["MixedCase"]})
    rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "dummy_transform_rule",
        "target_case": "lower",
        "severity": "INFO"
    })
    clean_df = rule.apply_transform(df)
    assert clean_df.at[0, "col"] == "mixedcase"

def test_transform_rule_missing_function():
    with pytest.raises(ValidationError, match="no 'function' path"):
        ConfigRule(**{"name": "bad_transform", "type": "transform"})

def test_transform_rule_bad_import():
    with pytest.raises(SecurityError, match="not in the active registry"):
        ConfigRule(**{
            "name": "bad_transform",
            "type": "transform",
            "function": "fake_module.fake_function"
        })

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
        "function": "dummy_transform_rule",
        "severity": "INFO"
    })
    validator = DataValidator([r1, r2])
    clean_df = validator.clean(df, strict=True)
    assert len(clean_df) == 2
    assert clean_df.index.tolist() == [0, 2]
    assert clean_df.at[0, "col"] == "LOWER"
    assert clean_df.at[2, "col"] == "MIXEDCASE"

def test_from_config_yaml_error(tmp_path):
    bad_yaml = tmp_path / "bad_syntax.yaml"
    with open(bad_yaml, "w") as f:
        f.write("] : invalid : yaml : [")
    with pytest.raises(ValueError, match="Config parse failed"):
        DataValidator.from_config(str(bad_yaml), rules_dir="dummy")

def test_from_config_validation_error(tmp_path):
    bad_schema = tmp_path / "bad_schema.yaml"
    with open(bad_schema, "w") as f:
        yaml.dump({"rules": [{"name": "r1", "type": "not_null", "severity": "SUPER_ERROR"}]}, f)
    with pytest.raises(ValidationError):
        DataValidator.from_config(str(bad_schema), rules_dir="dummy")

def test_evaluate_unknown_rule_type():
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{"name": "r1", "field": "A", "type": "not_null"})
    rule.type = "magic"
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
    res = ValidationResult(passed=True, total_rows_affected=10)
    assert res["passed"] is True
    assert res["total_rows_affected"] == 10
    with pytest.raises(KeyError):
        _ = res["does_not_exist"]

def test_from_config_empty_or_missing_rules(tmp_path):
    no_rules = tmp_path / "no_rules.yaml"
    no_rules.write_text("some_other_key: value")
    with pytest.raises(ValueError, match="YAML config must contain a 'profiles' or 'rules' key"):
        DataValidator.from_config(str(no_rules), rules_dir="dummy")
    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("")
    with pytest.raises(ValueError, match="YAML file is completely empty"):
        DataValidator.from_config(str(empty_yaml), rules_dir="dummy")

def test_evaluate_and_transform_without_field():
    df = pd.DataFrame({"A": [1, 2]})
    rule_custom = ConfigRule(**{
        "name": "custom_no_field",
        "type": "custom",
        "severity": "ERROR",
        "function": "dummy_custom_rule_no_field"
    })
    rule_transform = ConfigRule(**{
        "name": "transform_no_field",
        "type": "transform",
        "severity": "INFO",
        "function": "dummy_transform_no_field"
    })
    validator = DataValidator([rule_custom, rule_transform])
    report = validator.validate(df)
    assert report.passed is False
    assert report.sample_bad_rows['custom_no_field'][0]['failed_value'] is None
    clean_df = validator.clean(df)
    assert "injected_by_transform" in clean_df.columns

def test_failsafe_validate_skips_crashing_rule(caplog):
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{
        "name": "crash_eval",
        "type": "custom",
        "severity": "ERROR",
        "function": "crashing_custom_rule"
    })
    validator = DataValidator([rule])
    report = validator.validate(df)
    assert report.passed is False
    assert len(report.skipped_rules) == 1
    assert "crashed and DID NOT RUN" in caplog.text

def test_failsafe_clean_skips_crashing_rules(caplog):
    df = pd.DataFrame({"A": [1]})
    r1 = ConfigRule(**{"name": "crash_eval", "type": "custom", "severity": "ERROR",
                       "function": "crashing_custom_rule"})
    r2 = ConfigRule(**{"name": "crash_transform", "type": "transform", "severity": "INFO",
                       "function": "crashing_transform_rule"})
    with pytest.raises(RuntimeError, match="Cleaning aborted"):
        DataValidator([r1, r2]).clean(df, strict=True)
    clean_df = DataValidator([r1, r2], allow_rule_failures=True).clean(df, strict=True)
    assert len(clean_df) == 1
    assert "FATAL ERROR: Transform rule 'crash_transform' crashed" in caplog.text
    assert "crash_eval" in caplog.text and "DID NOT RUN" in caplog.text

def test_validation_result_config_version():
    res = ValidationResult(passed=True, total_rows_affected=0)
    assert res.config_version == 'unknown'

def test_rule_dependencies_suppression():
    df = pd.DataFrame({"qty": [pd.NA, 150, 50]})
    rule_a = ConfigRule(**{
        "name": "rule_a",
        "field": "qty",
        "type": "not_null",
        "severity": "ERROR"
    })
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
    report = validator.validate(df)
    err_counts = {err['rule']: err['count'] for err in report.errors}
    warn_counts = {warn['rule']: warn['count'] for warn in report.warnings}
    assert err_counts.get("rule_a") == 1
    assert warn_counts.get("rule_b") == 1
    clean_df = validator.clean(df, strict=False, target_rules=["rule_a", "rule_b"])
    assert len(clean_df) == 1
    assert clean_df.index[0] == 2

def test_rule_dependency_not_found_rejected_at_load():
    rule = ConfigRule(**{
        "name": "rule_b",
        "field": "A",
        "type": "not_null",
        "depends_on": ["missing_rule"]
    })
    with pytest.raises(ValueError, match="not defined in this config"):
        DataValidator([rule])

def test_validate_evaluates_transformed_working_copy():
    df = pd.DataFrame({"col": ["mixedCase"]})
    t_rule = ConfigRule(**{
        "name": "t1",
        "type": "transform",
        "function": "dummy_transform_rule",
        "target_case": "lower",
        "severity": "INFO"
    })
    v_rule = ConfigRule(**{
        "name": "v1",
        "field": "col",
        "type": "regex",
        "pattern": "^[a-z]+$",
        "severity": "ERROR"
    })
    validator = DataValidator([t_rule, v_rule])
    report = validator.validate(df)
    assert report.passed is True

def test_failsafe_validate_skips_crashing_transform_setup(caplog):
    df = pd.DataFrame({"A": [1]})
    rule = ConfigRule(**{
        "name": "crash_setup",
        "type": "transform",
        "severity": "INFO",
        "function": "crashing_transform_rule"
    })
    validator = DataValidator([rule])
    report = validator.validate(df)
    assert report.passed is True
    assert "FATAL ERROR: Transform 'crash_setup' crashed during validation setup" in caplog.text

def test_security_registry_blocks_unknown_function():
    with pytest.raises(SecurityError, match="not in the active registry"):
        ConfigRule(**{
            "name": "malicious_rule",
            "field": "col",
            "type": "custom",
            "function": "os.system"
        })

def test_detect_conflicts_intra_rule():
    rule = ConfigRule(**{
        "name": "impossible_range",
        "field": "qty",
        "type": "range",
        "min": 100,
        "max": 10,
        "severity": "ERROR"
    })
    with pytest.raises(ValueError, match="is impossible."):
        DataValidator([rule])

def test_detect_conflicts_inter_rule():
    rule_1 = ConfigRule(**{
        "name": "range_low",
        "field": "qty",
        "type": "range",
        "min": 0,
        "max": 50,
        "severity": "ERROR"
    })
    rule_2 = ConfigRule(**{
        "name": "range_high",
        "field": "qty",
        "type": "range",
        "min": 100,
        "max": 200,
        "severity": "ERROR"
    })
    with pytest.raises(ValueError, match="contradictory range rules"):
        DataValidator([rule_1, rule_2])

def test_detect_conflicts_exclusive_bounds():
    rule_1 = ConfigRule(**{
        "name": "r1",
        "field": "qty",
        "type": "range",
        "min": 0,
        "exclusive_min": True,
        "severity": "ERROR"
    })
    rule_2 = ConfigRule(**{
        "name": "r2",
        "field": "qty",
        "type": "range",
        "max": 0,
        "exclusive_max": True,
        "severity": "ERROR"
    })
    with pytest.raises(ValueError, match="contradictory range rules"):
        DataValidator([rule_1, rule_2])

def test_validation_result_rule_timings():
    df = pd.DataFrame({"A": [1, 2, 3]})
    rule = ConfigRule(**{"name": "speed_test_rule", "field": "A", "type": "not_null"})
    validator = DataValidator([rule])
    report = validator.validate(df)
    assert "speed_test_rule" in report.rule_timings
    assert isinstance(report.rule_timings["speed_test_rule"], float)
    slowest = report.slowest_rule
    assert slowest is not None
    assert slowest["rule"] == "speed_test_rule"
    assert "duration_seconds" in slowest
    assert slowest["duration_seconds"] >= 0.0

def test_validation_result_slowest_rule_empty():
    res = ValidationResult(passed=True, total_rows_affected=0, rule_timings={})
    assert res.slowest_rule is None

def test_filter_incremental_no_watermark():
    df = pd.DataFrame({"id": [1, 2, 3]})
    result = DataValidator.filter_incremental(df, "id", None)
    assert result.equals(df)

def test_filter_incremental_empty_dataframe():
    df = pd.DataFrame(columns=["id"])
    result = DataValidator.filter_incremental(df, "id", 10)
    assert result.empty

def test_filter_incremental_missing_column():
    df = pd.DataFrame({"other_col": [1, 2]})
    with pytest.raises(ValueError, match="Incremental column 'missing_col' missing from DataFrame"):
        DataValidator.filter_incremental(df, "missing_col", 1)

def test_filter_incremental_numeric_casting():
    df = pd.DataFrame({"id": [1, 2, 3, 4, 5]})
    result = DataValidator.filter_incremental(df, "id", "3")
    assert len(result) == 2
    assert result["id"].tolist() == [4, 5]

def test_filter_incremental_string_casting():
    df = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"]})
    result = DataValidator.filter_incremental(df, "date", "2024-01-01")
    assert len(result) == 2
    assert result["date"].tolist() == ["2024-01-02", "2024-01-03"]

def test_detect_conflicts_valid_overlapping_ranges():
    rule_1 = ConfigRule(**{"name": "r1", "field": "qty", "type": "range", "min": 10, "max": 20, "severity": "ERROR"})
    rule_2 = ConfigRule(**{"name": "r2", "field": "qty", "type": "range", "min": 5, "max": 25, "severity": "ERROR"})
    validator = DataValidator([rule_1, rule_2])
    assert len(validator.rules) == 2

def test_detect_conflicts_matching_bounds_carry_strictness():
    rule_1 = ConfigRule(**{
        "name": "r1", "field": "qty", "type": "range",
        "min": 10, "max": 20,
        "exclusive_min": False, "exclusive_max": False, "severity": "ERROR"
    })
    rule_2 = ConfigRule(**{
        "name": "r2", "field": "qty", "type": "range",
        "min": 10, "max": 20,
        "exclusive_min": True, "exclusive_max": True, "severity": "ERROR"
    })
    validator = DataValidator([rule_1, rule_2])
    assert len(validator.rules) == 2

def test_detect_conflicts_non_comparable_bounds():
    rule_1 = ConfigRule(**{"name": "r1", "field": "qty", "type": "range", "max": 50, "severity": "ERROR"})
    rule_2 = ConfigRule(**{"name": "r2", "field": "qty", "type": "range", "min": 10, "severity": "ERROR"})
    validator = DataValidator([rule_1, rule_2])
    assert len(validator.rules) == 2

def test_detect_conflicts_non_comparable_contradiction():
    rule_1 = ConfigRule(**{"name": "r1", "field": "qty", "type": "range", "max": 5, "severity": "ERROR"})
    rule_2 = ConfigRule(**{"name": "r2", "field": "qty", "type": "range", "min": 10, "severity": "ERROR"})
    with pytest.raises(ValueError, match="contradictory range rules"):
        DataValidator([rule_1, rule_2])

def test_crashed_rule_is_reported_and_fails_the_run():
    RULE_REGISTRY["boom"] = lambda df, **kwargs: 1/0
    try:
        rule = ConfigRule(name="boom_rule", field="q", type="custom",
                          function="boom", severity="ERROR")
        result = DataValidator([rule]).validate(pd.DataFrame({"q": [1, 2, 3]}))
        assert result.passed is False
        assert len(result.skipped_rules) == 1
        assert result.skipped_rules[0]["rule"] == "boom_rule"
        assert "ZeroDivisionError" in result.skipped_rules[0]["reason"]
    finally:
        RULE_REGISTRY.pop("boom", None)

def test_clean_aborts_when_a_rule_did_not_run():
    RULE_REGISTRY["boom"] = lambda df, **kwargs: 1/0
    try:
        rule = ConfigRule(name="boom_rule", field="q", type="custom",
                          function="boom", severity="ERROR")
        with pytest.raises(RuntimeError, match="Cleaning aborted"):
            DataValidator([rule]).clean(pd.DataFrame({"q": [1, 2, 3]}))
    finally:
        RULE_REGISTRY.pop("boom", None)

def test_custom_rule_without_function_key_rejected_at_load():
    with pytest.raises(ValueError, match="no 'function' path"):
        ConfigRule(name="typo_rule", field="q", type="custom")

def test_depends_on_unknown_rule_rejected_at_load():
    a = ConfigRule(name="range_rule", field="q", type="range", min=0,
                   depends_on=["does_not_exist"])
    with pytest.raises(ValueError, match="not defined in this config"):
        DataValidator([a])

def test_depends_on_forward_reference_rejected_at_load():
    dependent = ConfigRule(name="date_in_range", field="q", type="range", min=0,
                           depends_on=["parse_check"])
    dependency = ConfigRule(name="parse_check", field="q", type="not_null")
    with pytest.raises(ValueError, match="declared later"):
        DataValidator([dependent, dependency])
    DataValidator([dependency, dependent])

def test_circular_dependency_rejected_at_load():
    a = ConfigRule(name="A", field="q", type="not_null", depends_on=["B"])
    b = ConfigRule(name="B", field="q", type="not_null", depends_on=["A"])
    with pytest.raises(ValueError):
        DataValidator([a, b])

def test_duplicate_rule_names_rejected_at_load():
    a = ConfigRule(name="same", field="q", type="not_null")
    b = ConfigRule(name="same", field="q", type="range", min=0)
    with pytest.raises(ValueError, match="duplicate rule names"):
        DataValidator([a, b])

def test_crashed_rule_can_be_tolerated_explicitly(caplog):
    df = pd.DataFrame({"A": [1, 2]})
    rule = ConfigRule(**{
        "name": "crash_eval",
        "type": "custom",
        "severity": "ERROR",
        "function": "crashing_custom_rule"
    })
    validator = DataValidator([rule], allow_rule_failures=True)
    report = validator.validate(df)
    assert report.passed is True
    assert len(report.skipped_rules) == 1
    assert report.skipped_rules[0]["rule"] == "crash_eval"
    clean_df = validator.clean(df, strict=True)
    assert len(clean_df) == 2
    assert "crashed and DID NOT RUN during cleaning" in caplog.text

def test_from_config_profiles_default_fallback(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  default:
    rules:
      - name: r1
        field: col
        type: not_null
""")
    val = DataValidator.from_config(str(yaml_file), rules_dir="dummy")
    assert len(val.rules) == 1
    assert val.rules[0].name == "r1"

def test_from_config_profiles_no_default_raises(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  strict:
    rules:
      - name: r1
        field: col
        type: not_null
""")
    with pytest.raises(ValueError, match="No profile specified and no 'default' profile found."):
        DataValidator.from_config(str(yaml_file), rules_dir="dummy")

def test_from_config_profiles_not_found(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  default:
    rules: []
""")
    with pytest.raises(ValueError, match="Profile 'missing_profile' not found."):
        DataValidator.from_config(str(yaml_file), profile_name="missing_profile", rules_dir="dummy")

def test_from_config_profiles_inheritance(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  base:
    rules:
      - name: r1
        field: col
        type: not_null
      - name: r2
        field: qty
        type: range
        min: 0
  strict:
    inherits: base
    rules:
      - name: r2
        field: qty
        type: range
        min: 10
""")
    val = DataValidator.from_config(str(yaml_file), profile_name="strict", rules_dir="dummy")
    assert len(val.rules) == 2
    rule_names = {r.name: r for r in val.rules}
    assert "r1" in rule_names
    assert "r2" in rule_names
    assert rule_names["r2"].model_extra["min"] == 10

def test_from_config_profiles_parent_not_found(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  strict:
    inherits: missing_base
    rules: []
""")
    with pytest.raises(ValueError, match="Profile 'missing_base' not found."):
        DataValidator.from_config(str(yaml_file), profile_name="strict", rules_dir="dummy")

def test_list_profiles_success(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  default: {}
  strict: {}
""")
    profiles = DataValidator.list_profiles(str(yaml_file))
    assert profiles == ["default", "strict"]

def test_list_profiles_no_profiles_key(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("rules: []")
    profiles = DataValidator.list_profiles(str(yaml_file))
    assert profiles == []

def test_list_profiles_error():
    profiles = DataValidator.list_profiles("non_existent_file.yaml")
    assert profiles == []

def test_conditional_rule_evaluation():
    df = pd.DataFrame({
        "country": ["US", "US", "CA"],
        "zip": ["12345", "BAD", "123"]
    })
    rule = ConfigRule(**{
        "name": "us_zip",
        "type": "conditional",
        "condition_field": "country",
        "condition_value": "US",
        "field": "zip",
        "target_type": "regex",
        "pattern": "^[0-9]{5}$"
    })
    mask = rule.evaluate(df)
    assert mask.tolist() == [False, True, False]

def test_conditional_rule_missing_keys():
    rule = ConfigRule(**{
        "name": "bad_cond",
        "type": "conditional",
        "field": "zip"
    })
    with pytest.raises(ValueError, match="missing conditional keys"):
        rule.evaluate(pd.DataFrame({"zip": ["12345"]}))

def test_conditional_rule_missing_condition_field_in_df():
    df = pd.DataFrame({"zip": ["12345"]})
    rule = ConfigRule(**{
        "name": "cond",
        "type": "conditional",
        "condition_field": "country",
        "condition_value": "US",
        "field": "zip",
        "target_type": "not_null"
    })
    with pytest.raises(ValueError, match="Condition field 'country' missing from DataFrame"):
        rule.evaluate(df)

def test_per_rule_threshold_rejection():
    df = pd.DataFrame({"qty": [1, -1, -2, -3]})
    rule = ConfigRule(**{
        "name": "qty_rule",
        "field": "qty",
        "type": "range",
        "min": 0,
        "max_fail_pct": 0.50,
        "severity": "ERROR"
    })
    val = DataValidator([rule])
    report = val.validate(df)
    assert report.batch_rejected is True
    assert report.passed is False
    assert len(report.rejection_reasons) == 1
    assert "failed 75.0% of rows" in report.rejection_reasons[0]

def test_global_threshold_rejection():
    df = pd.DataFrame({"qty": [1, -1, 1, 1]})
    rule = ConfigRule(**{
        "name": "qty_rule",
        "field": "qty",
        "type": "range",
        "min": 0,
        "severity": "ERROR"
    })
    val = DataValidator([rule], global_max_fail_pct=0.20)
    report = val.validate(df)
    assert report.batch_rejected is True
    assert report.passed is False
    assert len(report.rejection_reasons) == 1
    assert "Global failure rate 25.0% exceeds threshold" in report.rejection_reasons[0]

def test_clean_aborts_on_rejected_batch():
    df = pd.DataFrame({"qty": [-1, -1]})
    rule = ConfigRule(**{
        "name": "qty_rule",
        "field": "qty",
        "type": "range",
        "min": 0,
        "max_fail_pct": 0.10,
        "severity": "ERROR"
    })
    val = DataValidator([rule])
    with pytest.raises(RuntimeError, match="Refusing to clean: Batch exceeded failure thresholds"):
        val.clean(df)

def test_from_config_drift_inheritance(tmp_path):
    yaml_file = tmp_path / "profiles.yaml"
    yaml_file.write_text("""
profiles:
  base:
    global_drift_abs_min: 0.05
    global_drift_rel_min: 0.75
    rules:
      - name: r1
        field: col
        type: not_null
  strict:
    inherits: base
    rules: []
""")
    val = DataValidator.from_config(str(yaml_file), profile_name="strict", rules_dir="dummy")
    assert val.global_drift_abs_min == 0.05
    assert val.global_drift_rel_min == 0.75

def test_validation_result_total_rows(sample_df, mock_yaml_config):
    validator = DataValidator.from_config(mock_yaml_config, rules_dir="dummy")
    report = validator.validate(sample_df)
    assert report.total_rows == 4

def test_validate_stream_basic(tmp_path):
    df = pd.DataFrame({"A": [1, 2, -1, -2, 5, -3]})
    csv_path = tmp_path / "stream_basic.csv"
    df.to_csv(csv_path, index=False)
    r1 = ConfigRule(**{"name": "r1", "field": "A", "type": "range", "min": 0, "severity": "ERROR"})
    r2 = ConfigRule(**{"name": "r2", "field": "A", "type": "range", "min": 0, "severity": "WARNING"})
    val = DataValidator([r1, r2])
    report = val.validate_stream(str(csv_path), chunksize=2)
    assert report.passed is False
    assert report.total_rows == 6
    assert report.total_rows_affected == 3
    assert len(report.sample_bad_rows['r1']) == 3
    indices = [s['row_index'] for s in report.sample_bad_rows['r1']]
    assert indices == [2, 3, 5]

def test_validate_stream_composite_and_thresholds(tmp_path):
    df = pd.DataFrame({
        "A": [1, 1, 1, 2, 3, 4],
        "B": [1, 1, 1, 2, 3, 4]
    })
    csv_path = tmp_path / "stream_comp.csv"
    df.to_csv(csv_path, index=False)
    rule = ConfigRule(**{
        "name": "composite_pk_unique",
        "type": "custom",
        "function": "check_composite_unique",
        "subset": ["A", "B"],
        "severity": "ERROR"
    })
    val = DataValidator([rule], global_max_fail_pct=0.20)
    report = val.validate_stream(str(csv_path), chunksize=2)
    assert report.batch_rejected is True
    assert len(report.rejection_reasons) == 1
    assert "exceeds threshold" in report.rejection_reasons[0]
    assert report.errors[0]["count"] == 3

def test_validate_stream_composite_missing_columns(tmp_path):
    df = pd.DataFrame({"A": [1, 2, 3]})
    csv_path = tmp_path / "stream_missing_cols.csv"
    df.to_csv(csv_path, index=False)
    rule = ConfigRule(**{
        "name": "composite_pk_unique",
        "type": "custom",
        "function": "check_composite_unique",
        "subset": ["A", "B"],
        "severity": "ERROR"
    })
    val = DataValidator([rule])
    report = val.validate_stream(str(csv_path), chunksize=2)
    assert report.passed is True
    assert report.total_rows_affected == 0

def test_validate_stream_sample_cap(tmp_path):
    df = pd.DataFrame({"A": [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]})
    csv_path = tmp_path / "stream_cap.csv"
    df.to_csv(csv_path, index=False)
    r1 = ConfigRule(**{"name": "r1", "field": "A", "type": "range", "min": 0, "severity": "ERROR"})
    val = DataValidator([r1])
    report = val.validate_stream(str(csv_path), chunksize=3)
    assert report.errors[0]["count"] == 10
    assert len(report.sample_bad_rows['r1']) == 5

def test_evaluate_transform_rule():
    df = pd.DataFrame({"A": [1, 2]})
    rule = ConfigRule(name="t1", type="transform", function="dummy_transform_no_field")
    mask = rule.evaluate(df)
    assert mask.sum() == 0

def test_detect_conflicts_max_less_than_prev_max():
    r1 = ConfigRule(name="r1", field="q", type="range", max=50)
    r2 = ConfigRule(name="r2", field="q", type="range", max=20)
    r3 = ConfigRule(name="r3", field="w", type="range", min=10)
    r4 = ConfigRule(name="r4", field="w", type="range", min=20)
    val = DataValidator([r1, r2, r3, r4])
    assert len(val.rules) == 4

def test_filter_incremental_pure_string_casting():
    df = pd.DataFrame({"id": ["A", "B", "C"]})
    result = DataValidator.filter_incremental(df, "id", "A")
    assert len(result) == 2

def test_validate_stream_empty_chunks_via_watermark(tmp_path):
    df = pd.DataFrame({"A": [1, 2], "wm": [1, 2]})
    csv_path = tmp_path / "empty_stream.csv"
    df.to_csv(csv_path, index=False)
    rule = ConfigRule(name="r1", field="A", type="not_null")
    val = DataValidator([rule])
    report = val.validate_stream(str(csv_path), chunksize=1, watermark_col="wm", current_watermark=5)
    assert report.total_rows == 0

def test_validate_stream_transform_crash_pass_1(tmp_path):
    df = pd.DataFrame({"A": [1, 2], "B": [1, 2]})
    csv_path = tmp_path / "stream_crash.csv"
    df.to_csv(csv_path, index=False)
    rule_pk = ConfigRule(name="composite_pk_unique", type="custom",
                         function="check_composite_unique", subset=["A", "B"])
    rule_t = ConfigRule(name="t1", type="transform", function="crashing_transform_rule")
    val = DataValidator([rule_pk, rule_t])
    report = val.validate_stream(str(csv_path), chunksize=2)
    assert report.passed is True

def test_validate_dependency_not_executed(caplog):
    df = pd.DataFrame({"A": [1]})
    r1 = ConfigRule(name="crash_rule", type="custom", function="crashing_custom_rule",
                    severity="ERROR")
    r2 = ConfigRule(name="dep_rule", field="A", type="not_null", depends_on=["crash_rule"])
    val = DataValidator([r1, r2], allow_rule_failures=True)
    val.validate(df)
    assert "not found or not executed yet" in caplog.text

def test_clean_transform_crashes(caplog):
    df = pd.DataFrame({"A": [1]})
    r_t = ConfigRule(name="crash_t", type="transform", function="crashing_transform_rule")
    val = DataValidator([r_t])
    dummy_report = ValidationResult(passed=True, total_rows_affected=0)
    val.clean(df, val_report=dummy_report)
    assert "FATAL ERROR: Transform rule 'crash_t' crashed" in caplog.text

def test_clean_dependency_not_executed(caplog):
    df = pd.DataFrame({"A": [1]})
    r1 = ConfigRule(name="crash_rule", type="custom", function="crashing_custom_rule",
                    severity="ERROR")
    r2 = ConfigRule(name="dep_rule", field="A", type="not_null", depends_on=["crash_rule"])
    val = DataValidator([r1, r2], allow_rule_failures=True)
    dummy_report = ValidationResult(passed=True, total_rows_affected=0)
    val.clean(df, val_report=dummy_report)
    assert "not found/executed" in caplog.text

def test_evaluate_and_transform_without_field_explicit_fallback():
    df = pd.DataFrame({"A": [1]})
    rule_custom = ConfigRule(
        name="custom_no_field_2", type="custom", severity="ERROR",
        function="dummy_custom_rule_no_field"
    )
    val = DataValidator([rule_custom])
    report = val.validate(df)
    assert report.passed is False

def _error_counts(report):
    return {e["rule"]: e["count"] for e in report.errors}

def test_stream_matches_in_memory_and_leaves_validator_unchanged(tmp_path):
    rows = []
    for i in range(100):
        sku = f"SKU-{1000 + i:04d}" if i >= 10 else f"BAD-{i}"
        rows.append({
            "date": "2024-01-01", "sku_id": sku, "warehouse_id": "WH-01",
            "quantity_sold": 5, "unit_price": 20.0,
        })
    df = pd.DataFrame(rows)
    df.loc[95:99, ["date", "sku_id", "warehouse_id"]] = \
        df.loc[0:4, ["date", "sku_id", "warehouse_id"]].values

    csv_path = tmp_path / "equiv.csv"
    df.to_csv(csv_path, index=False)

    # Use the new dynamic registry
    RULE_REGISTRY["check_composite_unique"] = real_custom_rules.check_composite_unique
    RULE_REGISTRY["check_composite_unique_stream"] = real_custom_rules.check_composite_unique_stream

    try:
        rules = [
            ConfigRule(name="sku_format", field="sku_id", type="regex",
                       pattern="^SKU-[0-9]{4}$", severity="ERROR", max_fail_pct=0.05),
            ConfigRule(**{
                "name": "composite_pk_unique", "type": "custom",
                "function": "check_composite_unique",
                "subset": ["date", "sku_id", "warehouse_id"], "severity": "ERROR",
            }),
        ]
        val = DataValidator(rules, global_max_fail_pct=0.50)

        in_memory = val.validate(pd.read_csv(csv_path))
        streamed = val.validate_stream(str(csv_path), chunksize=25)

        assert streamed.batch_rejected == in_memory.batch_rejected
        assert sorted(streamed.rejection_reasons) == sorted(in_memory.rejection_reasons)
        assert _error_counts(streamed) == _error_counts(in_memory)

        assert [r.model_extra.get("function") for r in val.rules if r.name == "composite_pk_unique"] == \
               ["check_composite_unique"]
        after = val.validate(pd.read_csv(csv_path))
        assert _error_counts(after) == _error_counts(in_memory)
    finally:
        RULE_REGISTRY.pop("check_composite_unique", None)
        RULE_REGISTRY.pop("check_composite_unique_stream", None)


def test_validate_row_dict_mixed_results():
    """Tests proper bucketing of errors, warnings, info, and skipped rules from a dictionary."""
    row = {"req": "value", "rng": 15, "inf": "fail_regex", "pk": 1}

    r_err = ConfigRule(name="err_rule", field="req", type="not_null", severity="ERROR")
    r_warn = ConfigRule(name="warn_rule", field="rng", type="range", min=0, max=10, severity="WARNING")
    r_info = ConfigRule(name="info_rule", field="inf", type="regex", pattern="^pass$", severity="INFO")
    r_skip1 = ConfigRule(name="skip1", field="req", type="unique")
    r_skip2 = ConfigRule(name="composite_pk_unique", type="custom", function="dummy_custom_rule")

    val = DataValidator([r_err, r_warn, r_info, r_skip1, r_skip2])
    res = val.validate_row(row)

    assert res.passed is True  # No ERROR rules failed (req is not null)
    assert "err_rule" not in res.errors
    assert "warn_rule" in res.warnings
    assert "info_rule" in res.info
    assert "skip1" in res.skipped_stateful
    assert "composite_pk_unique" in res.skipped_stateful


def test_validate_row_json_string_success():
    """Tests parsing a valid JSON string."""
    val = DataValidator([ConfigRule(name="r1", field="A", type="not_null", severity="ERROR")])
    res = val.validate_row('{"A": 1}')

    assert res.passed is True
    assert len(res.errors) == 0


def test_validate_row_json_string_failure():
    """Tests the ValueError raised upon receiving malformed JSON."""
    val = DataValidator([ConfigRule(name="r1", field="A", type="not_null", severity="ERROR")])
    with pytest.raises(ValueError, match="Failed to parse JSON string"):
        val.validate_row('{"A": 1')


def test_validate_row_crashing_transform(caplog):
    """Tests that a crashing transform does not crash the entire real-time pipeline."""
    r_t = ConfigRule(name="crash_t", type="transform", function="crashing_transform_rule")
    val = DataValidator([r_t])
    res = val.validate_row({"A": 1})

    assert res.passed is True
    assert "crashed during real-time setup" in caplog.text


def test_validate_row_crashing_evaluate(caplog):
    """Tests that a crashing rule evaluation does not halt execution."""
    r_e = ConfigRule(name="crash_e", type="custom", function="crashing_custom_rule", severity="ERROR")
    val = DataValidator([r_e])
    res = val.validate_row({"A": 1})

    assert res.passed is True
    assert "crash_e" not in res.errors
    assert "crashed during real-time validation" in caplog.text


def test_validate_row_dependencies():
    """Tests that dependent rules are masked out if the parent rule fails."""
    r_a = ConfigRule(name="r_a", field="qty", type="not_null", severity="ERROR")
    r_b = ConfigRule(name="r_b", field="qty", type="range", min=0, max=100, severity="ERROR", depends_on=["r_a"])
    val = DataValidator([r_a, r_b])

    # Null qty fails r_a. Since r_b depends on r_a, r_b should NOT report an error.
    res = val.validate_row({"qty": None})

    assert res.passed is False
    assert "r_a" in res.errors
    assert "r_b" not in res.errors


def test_validate_row_missing_dependency(caplog):
    """Tests fallback logic when a dependency mask is unexpectedly missing."""
    r_eval = ConfigRule(name="r_eval", field="A", type="not_null", severity="ERROR")
    val = DataValidator([r_eval])

    # Dynamically inject dependency to bypass initialization checks
    val.rules[0].depends_on = ["ghost_rule"]
    res = val.validate_row({"A": None})

    assert res.passed is False
    assert "r_eval" in res.errors
    assert "Dependency 'ghost_rule' for rule 'r_eval' not found" in caplog.text