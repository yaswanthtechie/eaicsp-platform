"""
Permanent, append-only audit archive of profiling runs.

Storage is JSON Lines: one run per line. A new run is APPENDED and old
lines are never rewritten, so a crash, a full disk or a bad manual edit
can at worst damage the line being written, never the history before it.

Reads fail closed: if any existing line cannot be parsed, an
AuditArchiveError is raised instead of pretending the archive is empty.
(Pretending it was empty is what used to let the next save wipe history.)
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

# Stops two threads in the same process interleaving half-written lines.
_write_lock = threading.Lock()


class AuditArchiveError(RuntimeError):
    """The archive exists but cannot be read safely."""


class AuditArchive:

    def __init__(self, archive_file=None):
        base_dir = Path(__file__).resolve().parent.parent

        if archive_file is None:
            self.archive_file = (
                base_dir / "reports" / "audit_archive.jsonl"
            )
        else:
            self.archive_file = Path(archive_file)

    def load_archive(self):
        """
        Return every archived run, oldest first.

        Raises AuditArchiveError if the file cannot be read or any line is
        damaged, so the problem is noticed and repaired, never hidden.
        """
        if not self.archive_file.exists():
            return []

        records = []

        try:
            with open(
                self.archive_file,
                "r",
                encoding="utf-8",
            ) as file:
                for line_number, line in enumerate(file, start=1):
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise AuditArchiveError(
                            f"Audit archive {self.archive_file} is damaged "
                            f"at line {line_number}. Refusing to continue so "
                            "no history is lost. Restore the file from "
                            "backup, or remove only the damaged line."
                        ) from exc

                    if (
                        not isinstance(record, dict)
                        or "run_id" not in record
                    ):
                        raise AuditArchiveError(
                            f"Audit archive {self.archive_file} line "
                            f"{line_number} is not a valid audit record."
                        )

                    records.append(record)

        except OSError as exc:
            raise AuditArchiveError(
                f"Audit archive {self.archive_file} cannot be read: {exc}"
            ) from exc

        return records

    def save_run(self, report, drift=None):
        """
        Append one run to the archive. Existing records are never rewritten.
        """
        if not isinstance(report, dict):
            raise TypeError(
                "report must be a dictionary"
            )

        run_record = {
            "run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "profile_report": report,
            "drift_report": drift,
        }

        line = json.dumps(run_record)

        self.archive_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with _write_lock:
            # If a previous write was cut off mid-line, start on a fresh
            # line so the new record is not glued onto the broken one.
            needs_newline = False

            if (
                self.archive_file.exists()
                and self.archive_file.stat().st_size > 0
            ):
                with open(self.archive_file, "rb") as existing:
                    existing.seek(-1, os.SEEK_END)
                    needs_newline = existing.read(1) != b"\n"

            with open(
                self.archive_file,
                "a",
                encoding="utf-8",
            ) as file:
                if needs_newline:
                    file.write("\n")

                file.write(line + "\n")
                file.flush()
                os.fsync(file.fileno())

        return run_record

    def get_run_by_id(self, run_id):
        """
        Return a single audit record by run ID.
        """
        if not run_id:
            raise ValueError("run_id must be provided")

        archive = self.load_archive()

        for record in archive:
            if record.get("run_id") == run_id:
                return record

        return None

    def query_runs(
        self,
        drift_status=None,
        min_quality_score=None,
        max_quality_score=None,
        start_time=None,
        end_time=None,
    ):
        """
        Query historical audit records using simple filters.

        start_time / end_time without a timezone are treated as UTC,
        because every record is stored in UTC.
        """
        start_time = _as_utc(start_time)
        end_time = _as_utc(end_time)

        archive = self.load_archive()

        results = []

        for record in archive:
            profile_report = record.get(
                "profile_report",
                {}
            )

            quality_score = (
                profile_report
                .get("quality_score", {})
                .get("score")
            )

            record_time = datetime.fromisoformat(
                record["timestamp"]
            )

            if (
                start_time is not None
                and record_time < start_time
            ):
                continue

            if (
                end_time is not None
                and record_time > end_time
            ):
                continue

            if (
                drift_status is not None
                and (
                    not record.get("drift_report")
                    or record["drift_report"].get("status")
                    != drift_status
                )
            ):
                continue

            if (
                min_quality_score is not None
                and (
                    quality_score is None
                    or quality_score < min_quality_score
                )
            ):
                continue

            if (
                max_quality_score is not None
                and (
                    quality_score is None
                    or quality_score > max_quality_score
                )
            ):
                continue

            results.append(record)

        return results


def _as_utc(value):
    """Treat a naive datetime as UTC so comparisons never raise TypeError."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value