import textwrap
from pathlib import Path

import pandas as pd
import pytest

from src.registry import RULE_REGISTRY, DEFAULT_RULES_DIR, clear_registry, discover_rules, register_rule
from src.validator import DataValidator

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ZIP_RULE = '''
from src.registry import register_rule

@register_rule()
def check_zip5(df, *, field, **kwargs):
    """ZIP code must be exactly 5 digits."""
    return ~df[field].astype(str).str.fullmatch(r"[0-9]{5}")
'''


@pytest.fixture
def empty_registry():
    clear_registry()
    yield
    clear_registry()


def write(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_dropped_in_rule_file_is_discovered_and_runs(tmp_path, empty_registry):
    """The stretch goal itself: a brand-new file in a rules folder works with no code changes."""
    rules_dir = tmp_path / "my_rules"
    write(rules_dir, "zip_rule.py", ZIP_RULE)
    config = tmp_path / "zip.yaml"
    config.write_text(textwrap.dedent('''
        version: "1"
        profiles:
          default:
            rules:
              - name: zip5
                type: custom
                field: zip
                severity: ERROR
                function: check_zip5
    '''), encoding="utf-8")

    validator = DataValidator.from_config(str(config), rules_dir=str(rules_dir))
    report = validator.validate(pd.DataFrame({"zip": ["12345", "ABCDE", "9876"]}))

    assert "check_zip5" in RULE_REGISTRY
    assert report.errors == [{"rule": "zip5", "field": "zip", "count": 2}]


def test_rule_files_in_subfolders_are_discovered(tmp_path, empty_registry):
    write(tmp_path / "rules" / "geo", "zip_rule.py", ZIP_RULE)
    discover_rules(tmp_path / "rules")
    assert "check_zip5" in RULE_REGISTRY


def test_same_name_in_two_files_raises(tmp_path, empty_registry):
    write(tmp_path / "rules", "a.py", ZIP_RULE)
    write(tmp_path / "rules", "b.py", ZIP_RULE)
    with pytest.raises(ValueError, match="already registered"):
        discover_rules(tmp_path / "rules")


def test_broken_rule_file_fails_loudly(tmp_path, empty_registry):
    write(tmp_path / "rules", "broken.py", "def oops(:\n")
    with pytest.raises(SyntaxError):
        discover_rules(tmp_path / "rules")


def test_force_reload_does_not_report_a_collision(tmp_path, empty_registry):
    rules_dir = tmp_path / "rules"
    write(rules_dir, "zip_rule.py", ZIP_RULE)
    discover_rules(rules_dir)
    first = RULE_REGISTRY["check_zip5"]

    discover_rules(rules_dir, force_reload=True)

    assert RULE_REGISTRY["check_zip5"] is not first


def test_normal_import_then_discovery_does_not_collide(empty_registry):
    import importlib
    import rules.custom_rules

    importlib.reload(rules.custom_rules)  # registers via the normal import system
    discover_rules(DEFAULT_RULES_DIR)  # executes the same file again under another module name
    assert "check_negatives" in RULE_REGISTRY


def test_register_rule_with_explicit_name(empty_registry):
    @register_rule("renamed_rule")
    def some_function(df, **kwargs):
        return df.iloc[:, 0].isna()

    assert RULE_REGISTRY["renamed_rule"] is some_function


def test_default_rules_dir_does_not_depend_on_cwd(tmp_path, monkeypatch, empty_registry):
    """Library callers who don't pass rules_dir must still find the packaged rules."""
    monkeypatch.chdir(tmp_path)
    validator = DataValidator.from_config(str(PROJECT_ROOT / "configs" / "sales_rules.yaml"))
    assert any(r.name == "composite_pk_unique" for r in validator.rules)


def test_missing_rules_dir_only_warns(tmp_path, empty_registry, caplog):
    discover_rules(tmp_path / "does_not_exist")
    assert "Skipping auto-discovery" in caplog.text