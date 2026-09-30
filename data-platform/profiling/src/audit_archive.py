import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class AuditArchive:

    def __init__(self, archive_file=None):
        base_dir = Path(__file__).resolve().parent.parent

        if archive_file is None:
            self.archive_file = (
                base_dir / "reports" / "audit_archive.json"
            )
        else:
            self.archive_file = Path(archive_file)

    def load_archive(self):
        if not self.archive_file.exists():
            return []

        try:
            with open(
                self.archive_file,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, list):
                return []

            return data

        except (json.JSONDecodeError, OSError):
            return []

    def save_run(self, report, drift=None):
        if not isinstance(report, dict):
            raise TypeError(
                "report must be a dictionary"
            )

        archive = self.load_archive()

        run_record = {
            "run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "schema_version": "1.0",
            "profile_report": report,
            "drift_report": drift,
        }

        archive.append(run_record)

        self.archive_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_file = self.archive_file.with_suffix(
            ".tmp"
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                archive,
                file,
                indent=4,
            )

        temp_file.replace(self.archive_file)

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
        """
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