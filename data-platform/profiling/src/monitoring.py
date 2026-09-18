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
            "quality_scorecard": report.get("quality_scorecard", {}),
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

    def get_scorecard_trend(self):
        history = self.load_history()

        if not history:
            return {
                "batches": 0,
                "overall_scores": [],
                "components": {
                    "completeness": [],
                    "validity": [],
                    "consistency": [],
                    "uniqueness": []
                },
                "trend": "No Data"
            }

        overall_scores = []
        components = {
            "completeness": [],
            "validity": [],
            "consistency": [],
            "uniqueness": []
        }

        for batch in history:
            scorecard = batch.get("quality_scorecard", {})

            if not scorecard:
                continue

            overall_score = scorecard.get("overall_score")

            if overall_score is not None:
                overall_scores.append(overall_score)

            component_scores = scorecard.get("components", {})

            for component in components:
                value = component_scores.get(component)

                if value is not None:
                    components[component].append(value)

        if len(overall_scores) < 2:
            trend = "Not Enough Data"

        elif overall_scores[-1] > overall_scores[0]:
            trend = "Improving"

        elif overall_scores[-1] < overall_scores[0]:
            trend = "Declining"

        else:
            trend = "Stable"

        return {
            "batches": len(overall_scores),
            "overall_scores": overall_scores,
            "components": components,
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

    def compare_runs(
        self,
        metric,
        last_n=5,
        slope_threshold=0.3,
        min_runs_for_drift=5,
    ):
        history = self.load_history()

        if not history:
            return {
                "metric": metric,
                "runs": 0,
                "values": [],
                "change": None,
                "slope": None,
                "trend": "No Data",
                "gradual_drift": False
            }

        recent_history = history[-last_n:]

        values = []

        for batch in recent_history:
            if metric in batch:
                values.append(batch[metric])

        if len(values) < 2:
            return {
                "metric": metric,
                "runs": len(values),
                "values": values,
                "change": None,
                "slope": None,
                "trend": "Not Enough Data",
                "gradual_drift": False
            }

        change = values[-1] - values[0]

        # Calculate least-squares slope across all runs.
        x_values = list(range(len(values)))
        x_mean = sum(x_values) / len(x_values)
        y_mean = sum(values) / len(values)

        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(x_values, values)
        )

        denominator = sum(
            (x - x_mean) ** 2
            for x in x_values
        )

        slope = numerator / denominator

        if slope > slope_threshold:
            trend = "Increasing"
        elif slope < -slope_threshold:
            trend = "Decreasing"
        else:
            trend = "Stable"

        return {
            "metric": metric,
            "runs": len(values),
            "values": values,
            "change": change,
            "slope": slope,
            "trend": trend,
            "gradual_drift": (
                trend != "Stable"
                and len(values) >= min_runs_for_drift
            )
        }