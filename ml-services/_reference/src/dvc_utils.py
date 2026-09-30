"""
DVC metadata helpers.

Reads the DVC-tracked reference dataset version so that
MLflow runs can be linked to the exact dataset contents.
"""

from pathlib import Path
import re


DVC_DATA_FILE = Path("data/reference/iris.csv.dvc")


def get_dvc_data_metadata() -> dict[str, str]:
    """
    Read the DVC metadata for the reference training dataset.

    Returns
    -------
    dict
        DVC path and content hash.

    Raises
    ------
    FileNotFoundError
        If the DVC metadata file does not exist.
    ValueError
        If the DVC hash cannot be found.
    """

    if not DVC_DATA_FILE.exists():
        raise FileNotFoundError(
            f"DVC metadata file not found: {DVC_DATA_FILE}"
        )

    content = DVC_DATA_FILE.read_text(encoding="utf-8")

    match = re.search(
        r"md5:\s*([a-fA-F0-9]{32})",
        content,
    )

    if not match:
        raise ValueError(
            f"Could not find DVC MD5 hash in {DVC_DATA_FILE}"
        )

    return {
        "dvc_data_path": "data/reference/iris.csv",
        "dvc_data_hash": match.group(1),
        "dvc_metadata_file": str(DVC_DATA_FILE),
    }