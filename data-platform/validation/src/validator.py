import pandas as pd
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class Rule:
    """
    Decorator to register a function as a validation rule.
    Requires a validation function that returns a boolean Series (True = bad row).
    Optionally accepts a cleaning function that returns a modified DataFrame.
    """

    # ADDED: priority parameter (default is 50)
    def __init__(self, name: str, severity: str = "warning", cleaner: callable = None, priority: int = 50):
        self.name = name
        self.severity = severity
        self.cleaner = cleaner
        self.priority = priority

    def __call__(self, func):
        func._is_rule = True
        func.rule_name = self.name
        func.severity = self.severity
        func.cleaner = self.cleaner
        func.priority = self.priority
        return func


class DataValidator:
    def __init__(self, rules: list):
        # Sort rules by priority: Lowest numbers (e.g., 10) run before higher numbers (e.g., 90)
        self.rules = sorted(rules, key=lambda r: getattr(r, 'priority', 50))

    def validate(self, df: pd.DataFrame) -> dict:
        """Runs all rules and returns a structured health report."""
        report = {
            "total_rows_evaluated": len(df),
            "is_clean": True,
            "issues": {}
        }

        for r in self.rules:
            # The rule function returns a mask where True = bad row
            bad_mask = r(df)
            bad_count = int(bad_mask.sum())

            if bad_count > 0:
                if r.severity == "error":
                    report["is_clean"] = False

                # Grab up to 2 sample rows to give context in the report
                sample_rows = df[bad_mask].head(2).astype(str).to_dict(orient="records")

                report["issues"][r.rule_name] = {
                    "count": bad_count,
                    "severity": r.severity,
                    "sample_bad_rows": sample_rows
                }

        return report

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sequentially applies the cleaner function of each rule (if defined)."""
        df_clean = df.copy()

        for r in self.rules:
            if r.cleaner is not None:
                initial_len = len(df_clean)
                df_clean = r.cleaner(df_clean)
                dropped = initial_len - len(df_clean)
                if dropped > 0:
                    logger.info(f"Rule '{r.rule_name}' dropped {dropped} rows.")

        return df_clean