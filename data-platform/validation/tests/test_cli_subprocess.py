import subprocess
import sys
from pathlib import Path
import pytest

# Adjust this path based on where your tests/ folder is relative to src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = PROJECT_ROOT / "src" / "validate_cli.py"


@pytest.fixture
def test_config(tmp_path):
    """Provides a basic YAML config with a single 'not_null' rule for testing."""
    config_file = tmp_path / "test_rules.yaml"
    config_file.write_text("""
version: "1.0.0"
rules:
  - name: test_not_null
    field: target_col
    type: not_null
    severity: ERROR
    """)
    return config_file


def test_cli_exit_success(tmp_path, test_config):
    """Test Exit Code 0: Valid data passes validation completely."""
    input_csv = tmp_path / "clean_data.csv"
    output_json = tmp_path / "report.json"

    # Write clean data (no missing values in target_col)
    input_csv.write_text("target_col,other_col\n1,A\n2,B\n")

    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--file", str(input_csv), "--config", str(test_config), "--output",
         str(output_json)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Expected success (0), but got {result.returncode}. Stderr: {result.stderr}"
    assert output_json.exists(), "JSON report was not generated."


def test_cli_exit_validation_failed(tmp_path, test_config):
    """Test Exit Code 1: Valid execution, but data fails the quality gate."""
    input_csv = tmp_path / "dirty_data.csv"
    output_json = tmp_path / "report.json"

    # Write dirty data (missing value in target_col)
    input_csv.write_text("target_col,other_col\n,A\n2,B\n")

    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--file", str(input_csv), "--config", str(test_config), "--output",
         str(output_json)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 1, f"Expected validation failure (1), but got {result.returncode}. Stderr: {result.stderr}"
    assert output_json.exists(), "JSON report should still be generated for failed data."


def test_cli_exit_tool_error(tmp_path, test_config):
    """Test Exit Code 2: Tool crash due to a missing file (Tool Error)."""
    # Point to a file that does not exist
    missing_csv = tmp_path / "does_not_exist.csv"
    output_json = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--file", str(missing_csv), "--config", str(test_config), "--output",
         str(output_json)],
        capture_output=True,
        text=True
    )

    # Assuming you updated validate_cli.py to return 2 (EXIT_TOOL_ERROR) for missing files
    assert result.returncode == 2, f"Expected tool error (2), but got {result.returncode}. Stderr: {result.stderr}"