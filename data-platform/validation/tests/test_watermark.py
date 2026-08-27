import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Adjust the import path if your module structure is different
from src.watermark import WatermarkManager


def test_get_watermark_file_not_exists(tmp_path):
    """Verifies that attempting to read a non-existent watermark returns None."""
    filepath = tmp_path / "missing.json"
    wm = WatermarkManager(filepath)

    assert wm.get_watermark() is None


def test_get_watermark_valid_json(tmp_path):
    """Verifies that a correctly formatted JSON file returns the watermark value."""
    filepath = tmp_path / "watermark.json"
    filepath.write_text(json.dumps({"last_watermark": 9999}))

    wm = WatermarkManager(filepath)

    assert wm.get_watermark() == 9999


def test_get_watermark_invalid_json(tmp_path):
    """Verifies that a corrupted JSON file is caught safely and returns None."""
    filepath = tmp_path / "corrupt.json"
    filepath.write_text("{bad_json: true,}")  # Invalid syntax

    wm = WatermarkManager(filepath)

    assert wm.get_watermark() is None


def test_get_watermark_os_error(tmp_path):
    """Verifies that an unreadable file (OSError/PermissionError) is caught safely."""
    filepath = tmp_path / "watermark.json"
    filepath.write_text(json.dumps({"last_watermark": 12345}))

    wm = WatermarkManager(filepath)

    # Mock the built-in 'open' function to simulate a system-level read error
    with patch("builtins.open", side_effect=OSError("Simulated Permission Denied")):
        assert wm.get_watermark() is None


def test_set_watermark_creates_dir_and_file(tmp_path):
    """Verifies that setting a watermark correctly creates missing directories and writes the JSON."""
    # Define a deeply nested path that does not exist yet
    filepath = tmp_path / "nested" / "state" / "watermark.json"
    wm = WatermarkManager(filepath)

    # Set the watermark
    wm.set_watermark("2026-12-31")

    # Assert the parent directories and file were properly created
    assert filepath.exists()

    # Assert the JSON structure is exactly as expected
    with open(filepath, "r") as f:
        data = json.load(f)

    assert data == {"last_watermark": "2026-12-31"}