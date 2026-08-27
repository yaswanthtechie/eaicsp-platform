import json
import os
from datetime import datetime
from pathlib import Path


class MonitoringHistory:

    def __init__(self, history_file=None, max_batches=10):
        base_dir = Path(__file__).resolve().parent.parent

        if history_file is None:
            self.history_file = base_dir / "reports" / "history.json"
        else:
            self.history_file = Path(history_file)

        self.max_batches = max_batches

    def load_history(self):
        if not os.path.exists(self.history_file):
            return []

        try:
            with open(self.history_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return []


    def save_batch(self, report, drift=None):
        history = self.load_history()

        # Collect null percentage for every column
        null_rates = {
            column["column"]: column["null_percent"]
            for column in report.get("column_summary", [])
        }

        batch = {
            "timestamp": datetime.now().isoformat(),
            "quality_score": report["quality_score"]["score"],
            "missing_values": report["quality_score"]["missing_values"],
            "duplicate_rows": report["quality_score"]["duplicate_rows"],
            "total_outliers": report["quality_score"]["total_outliers"],
            "drift_status": drift["status"] if drift else "No Previous Batch",
            "null_rates": null_rates
        }

        history.append(batch)

        # Keep only the latest 10 batches
        history = history[-self.max_batches:]

        os.makedirs(
            os.path.dirname(self.history_file),
            exist_ok=True
        )

        temp_file = self.history_file.with_suffix(".tmp")

        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(history, file, indent=4)

        os.replace(temp_file, self.history_file)

        return history

    def get_trend(self):
        history = self.load_history()

        if not history:
            return {
                "batches": 0,
                "quality_scores": [],
                "trend": "No Data"
            }

        quality_scores = [
            batch["quality_score"]
            for batch in history
        ]

        if len(quality_scores) == 1:
            trend = "Not Enough Data"

        elif quality_scores[-1] > quality_scores[0]:
            trend = "Improving"

        elif quality_scores[-1] < quality_scores[0]:
            trend = "Declining"

        else:
            trend = "Stable"

        return {
            "batches": len(history),
            "quality_scores": quality_scores,
            "trend": trend
        }

    def get_quality_alert(self):
        """
        Check whether the quality score dropped by more than
        10 points between the two most recent runs.
        """

        history = self.load_history()

        if len(history) < 2:
            return {
                "status": "NO_DATA",
                "previous_score": None,
                "current_score": None,
                "drop": None,
            }

        previous_score = history[-2]["quality_score"]
        current_score = history[-1]["quality_score"]

        drop = previous_score - current_score

        if drop > 10:
            status = "CRITICAL"
        else:
            status = "OK"

        return {
            "status": status,
            "previous_score": previous_score,
            "current_score": current_score,
            "drop": drop,
        }

    def get_column_trend(self, column_name):
        history = self.load_history()

        if not history:
            return {
                "column": column_name,
                "values": []
                }

        values = []

        for batch in history:
            null_rates = batch.get("null_rates", {})

            if column_name in null_rates:
                values.append(null_rates[column_name])

        return {
            "column": column_name,
            "values": values
        }
