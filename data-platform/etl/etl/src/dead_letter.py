"""
R4 stretch: dead-letter handling.

A batch that fails the quality gate 3 times in a row (by filename) should
stop being silently rejected every night forever - it should move to a
permanent needs_manual_review/ folder instead. That requires remembering how
many times a given filename has failed *across* pipeline runs, so the count
is persisted to a small local JSON file rather than kept in memory.
"""

import json
from pathlib import Path

COUNTS_FILE = Path("data/.quality_failure_counts.json")

DEAD_LETTER_THRESHOLD = 3


def _load_counts():
    if COUNTS_FILE.exists():
        try:
            return json.loads(COUNTS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_counts(counts):
    COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    COUNTS_FILE.write_text(json.dumps(counts))


def record_failure(batch_file):
    """Increment and return the consecutive-failure count for this filename."""
    counts = _load_counts()
    counts[batch_file] = counts.get(batch_file, 0) + 1
    _save_counts(counts)
    return counts[batch_file]


def clear_failures(batch_file):
    """Reset the counter - called on success, or once a file has been
    dead-lettered (so a *new* file that happens to reuse the same name
    later starts its own fresh count)."""
    counts = _load_counts()
    if batch_file in counts:
        del counts[batch_file]
        _save_counts(counts)


def is_dead_letter(batch_file):
    return _load_counts().get(batch_file, 0) >= DEAD_LETTER_THRESHOLD
