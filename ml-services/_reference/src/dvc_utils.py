"""
Training-data version helpers.

The MLflow run records the MD5 of the exact file the model was trained
on, and whether it matches the version DVC recorded in dvc.lock. That
hash identifies the data version: `git log -p dvc.lock` shows which
commit produced it.
"""

import hashlib
from pathlib import Path

import yaml

from src.data import (
    PROCESSED_DATA_PATH,
    PROJECT_ROOT,
)


DVC_LOCK_PATH = PROJECT_ROOT / "dvc.lock"


def file_md5(path: Path) -> str:
    """
    Calculate the MD5 hash of a file's bytes.

    This is the same hash format recorded by DVC 3
    for the file content.
    """

    digest = hashlib.md5()

    with Path(path).open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1 << 16),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def dvc_lock_md5(
    relative_path: str,
    lock_path: Path = DVC_LOCK_PATH,
):
    """
    Return the MD5 recorded by dvc.lock for a stage output.

    Returns
    -------
    str | None
        The DVC-recorded MD5 or None if it cannot be found.
    """

    if not Path(lock_path).exists():
        return None

    lock = (
        yaml.safe_load(
            Path(lock_path).read_text(
                encoding="utf-8"
            )
        )
        or {}
    )

    for stage in (
        lock.get("stages") or {}
    ).values():

        for out in (
            stage.get("outs") or []
        ):

            if out.get("path") == relative_path:

                md5 = out.get("md5")

                return (
                    None
                    if md5 is None
                    else str(md5)
                )

    return None


def get_training_data_version(
    data_path: Path = PROCESSED_DATA_PATH,
    lock_path: Path = DVC_LOCK_PATH,
) -> dict:
    """
    Describe the exact training data file for MLflow tagging.

    Returns
    -------
    dict
        Contains:

        training_data_path
        training_data_md5
        dvc_lock_md5
        matches_dvc_lock
    """

    relative_path = (
        Path(data_path)
        .resolve()
        .relative_to(PROJECT_ROOT)
        .as_posix()
    )

    actual_md5 = file_md5(data_path)

    locked_md5 = dvc_lock_md5(
        relative_path,
        lock_path,
    )

    return {
        "training_data_path": relative_path,
        "training_data_md5": actual_md5,
        "dvc_lock_md5": (
            locked_md5
            or "not_found"
        ),
        "matches_dvc_lock": str(
            locked_md5 == actual_md5
        ).lower(),
    }