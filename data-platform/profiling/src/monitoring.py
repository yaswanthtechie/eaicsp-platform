import json
import os
from datetime import datetime


class MonitoringHistory:

    def __init__(self, history_file="reports/history.json", max_batches=10):
        self.history_file = history_file
        self.max_batches = max_batches

    def load_history(self):
        if not os.path.exists(self.history_file):
            return []

        with open(self.history_file, "r") as file:
            return json.load(file)

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

        with open(self.history_file, "w") as file:
            json.dump(history, file, indent=4)

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
