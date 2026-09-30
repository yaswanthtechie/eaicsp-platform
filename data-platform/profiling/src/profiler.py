import pandas as pd
import numpy as np
import math


from src.profile import profile, ProfileReport
from src.compare import compare, DriftReport
from src.monitoring import MonitoringHistory
from src.audit_archive import AuditArchive
from src.expected_profile import (
    create_expected_profile,
    benchmark_profile,
)
from src.relationships import discover_relationships as discover_relationships_between
from src.executive_summary import generate_executive_summary



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

    if isinstance(obj, (float, np.floating)):
        # NaN and infinity are not valid JSON; FastAPI would return a 500.
        if not math.isfinite(obj):
            return None
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



    def create_expected_profile(
        self,
        profile_report,
        row_count_tolerance_percent=5.0,
        quality_score_tolerance=5.0,
        null_rate_tolerance_points=2.0,
        numeric_tolerance_percent=10.0,
    ):
        expected_profile = create_expected_profile(
            profile_report=profile_report,
            row_count_tolerance_percent=(
                row_count_tolerance_percent
            ),
            quality_score_tolerance=(
                quality_score_tolerance
            ),
            null_rate_tolerance_points=(
                null_rate_tolerance_points
            ),
            numeric_tolerance_percent=(
                numeric_tolerance_percent
            ),
        )

        return make_json_serializable(
            expected_profile
        )

    def benchmark_profile(
        self,
        expected_profile,
        current_profile,
    ):
        result = benchmark_profile(
            expected_profile=expected_profile,
            current_profile=current_profile,
        )

        return make_json_serializable(result)

    def executive_summary(
        self,
        profiling_report,
        etl_output=None,
        validation_output=None,
    ):
        """
        Generate a one-paragraph executive summary
        from profiling and static platform outputs.
        """
        summary = generate_executive_summary(
            profiling_report=profiling_report,
            etl_output=etl_output,
            validation_output=validation_output,
        )

        return summary

    
    def monitor(self, df, previous_df=None):
        report = self.profile(df)

        drift = None

        if previous_df is not None:
            drift = self.compare(previous_df, df)

        # Existing monitoring history
        monitoring = MonitoringHistory()

        history = monitoring.save_batch(
            report=report,
            drift=drift,
        )

        # Permanent audit archive
        audit_archive = AuditArchive()

        audit_record = audit_archive.save_run(
            report=report,
            drift=drift,
        )

        return {
            "report": report,
            "drift": drift,
            "history": history,
            "audit": audit_record,
        }

    def query_audit_runs(
        self,
        drift_status=None,
        min_quality_score=None,
        max_quality_score=None,
        start_time=None,
        end_time=None,
    ):
        archive = AuditArchive()

        results = archive.query_runs(
            drift_status=drift_status,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            start_time=start_time,
            end_time=end_time,
        )

        return make_json_serializable(results)