import pandas as pd
import numpy as np

from src.profile import profile
from src.compare import compare
from src.monitoring import MonitoringHistory

class Profiler:

    def profile(self, df):
        report = profile(df)
        return self._make_json_serializable(report)

    def compare(self, df_old, df_new):
        drift_report = compare(df_old, df_new)
        return self._make_json_serializable(drift_report)

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

    def _make_json_serializable(self, obj):

        if isinstance(obj, dict):
            return {
                key: self._make_json_serializable(value)
                for key, value in obj.items()
            }

        if isinstance(obj, list):
            return [
                self._make_json_serializable(value)
                for value in obj
            ]

        if isinstance(obj, tuple):
            return [
                self._make_json_serializable(value)
                for value in obj
            ]

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()

        if isinstance(obj, np.integer):
            return int(obj)

        if isinstance(obj, np.floating):
            return float(obj)

        return obj