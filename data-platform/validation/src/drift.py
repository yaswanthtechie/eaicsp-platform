import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from src.validator import DataValidator, ValidationResult

logger = logging.getLogger(__name__)


class ReportComparator:
    def __init__(self, history_dir: str = ".history", rolling_n: int = 10):
        self.history_dir = Path(history_dir)
        self.rolling_n = rolling_n
        self.history_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_rule_fail_rate(report_dict: Dict[str, Any], rule_name: str) -> float:
        """Calculates the failure rate for a specific rule from a report dictionary."""
        total_rows = report_dict.get("total_rows", 0)
        if total_rows == 0:
            return 0.0

        count = 0
        for issue in report_dict.get("errors", []) + report_dict.get("warnings", []):
            if issue.get("rule") == rule_name:
                count += issue.get("count", 0)

        return count / total_rows

    def _load_history(self) -> List[Dict[str, Any]]:
        """Loads up to the last `rolling_n` validation reports, sorted chronologically."""
        files = sorted(self.history_dir.glob("report_*.json"))
        recent_files = files[-self.rolling_n:]

        history = []
        for f in recent_files:
            try:
                with open(f, "r") as file:
                    history.append(json.load(file))
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load historical report {f.name}: {e}")
        return history

    def save_report(self, report: ValidationResult):
        """Saves the current report to the history directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.history_dir / f"report_{timestamp}.json"

        try:
            # Atomic write: Pydantic natively creates the JSON string BEFORE opening the file
            filepath.write_text(report.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save validation history to {filepath}: {e}")

    def evaluate_drift(self, current_report: ValidationResult, validator: DataValidator) -> List[str]:
        """Compares current failure rates against immediate and rolling baselines."""
        history = self._load_history()
        alerts = []

        if not history:
            logger.info("No historical reports found. Saving first report as baseline.")
            return alerts

        current_dict = current_report.model_dump()

        for rule in validator.rules:
            if rule.type == "transform":
                continue

            current_rate = self._get_rule_fail_rate(current_dict, rule.name)

            # Extract historical rates
            historical_rates = [self._get_rule_fail_rate(h, rule.name) for h in history]

            # Check if this rule has ever been evaluated in history
            # FIX: Pair 'historical_rates' and 'history' together using zip()
            if all(r == 0.0 and h.get("total_rows", 0) == 0 for r, h in zip(historical_rates, history)):
                logger.info(
                    f"Baseline initializing for rule '{rule.name}' - first observation, drift comparison begins once enough history exists.")
                continue

            last_rate = historical_rates[-1]
            rolling_rate = sum(historical_rates) / len(historical_rates) if historical_rates else 0.0

            # Determine applicable thresholds
            abs_min = rule.drift_abs_min if rule.drift_abs_min is not None else validator.global_drift_abs_min
            rel_min = rule.drift_rel_min if rule.drift_rel_min is not None else validator.global_drift_rel_min

            # Evaluation Helper
            def check_thresholds(baseline_rate: float, context: str):
                delta_abs = current_rate - baseline_rate
                if baseline_rate > 0:
                    delta_rel = delta_abs / baseline_rate
                else:
                    delta_rel = float('inf') if delta_abs > 0 else 0.0

                if delta_abs > abs_min and delta_rel > rel_min:
                    alerts.append(
                        f"Drift Alert ({context}): Rule '{rule.name}' failure rate jumped to {current_rate:.2%} "
                        f"(Baseline: {baseline_rate:.2%} | Rel increase: {delta_rel:.2%} | Abs increase: {delta_abs:.2%})"
                    )

            check_thresholds(last_rate, "vs Last Run")
            if len(history) > 1:
                check_thresholds(rolling_rate, f"vs Rolling Avg (n={len(history)})")

        return alerts