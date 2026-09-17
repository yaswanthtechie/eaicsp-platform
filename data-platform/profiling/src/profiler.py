import pandas as pd
import numpy as np

from src.profile import profile, ProfileReport
from src.compare import compare, DriftReport
from src.monitoring import MonitoringHistory
from src.relationships import discover_relationships as discover_relationships_between


def make_json_serializable(obj):
    if isinstance(obj, dict):
        return {
            make_json_serializable(key): make_json_serializable(value)
            for key, value in obj.items()
        }

    if isinstance(obj, list):
        return [
            make_json_serializable(value)
            for value in obj
        ]

    if isinstance(obj, tuple):
        return [
            make_json_serializable(value)
            for value in obj
        ]

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    return obj


class Profiler:

    def profile(self, df):
        report = profile(df)
        report = make_json_serializable(report)
        return ProfileReport(report)

    def compare(self, df_old, df_new):
        drift_report = compare(df_old, df_new)
        drift_report = make_json_serializable(drift_report)
        return DriftReport(drift_report)

    def discover_relationships(self, df_left, df_right):
        relationships = discover_relationships_between(
            df_left,
            df_right
        )

        return make_json_serializable(relationships)

    def monitor(self, df, previous_df=None):
        # Profile current batch
        report = self.profile(df)

        # Compare with previous batch if available
        drift = None

        if previous_df is not None:
            drift = self.compare(previous_df, df)

        # Save monitoring history
        monitoring = MonitoringHistory()

        history = monitoring.save_batch(
            report=report,
            drift=drift
        )

        return {
            "report": report,
            "drift": drift,
            "history": history
        }