import math
import re
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import types as sqltypes
from sqlalchemy import (
    create_engine,
    inspect,
    select,
    func,
    text,
    column as sa_column,
    table as sa_table,
    literal_column,
)
from src.profile import ProfileReport


def _is_numeric_type(col_type) -> bool:
    return isinstance(col_type, (sqltypes.Integer, sqltypes.Numeric))


def _is_date_type(col_type) -> bool:
    return isinstance(col_type, (sqltypes.Date, sqltypes.DateTime, sqltypes.Time))


def _needs_text_cast(col_type) -> bool:
    return isinstance(col_type, (sqltypes.JSON, sqltypes.ARRAY))


class PostgresPushdownProfiler:
    """Profiles PostgreSQL tables using direct SQL query pushdown."""

    def __init__(self, connection_or_url: Union[Engine, str]):
        if isinstance(connection_or_url, str):
            self.engine = create_engine(connection_or_url)
        else:
            self.engine = connection_or_url

    def profile_table(
        self,
        table_name: str,
        schema: str = "public",
        sample_rows_for_pii: int = 20,
    ) -> ProfileReport:
        inspector = inspect(self.engine)

        if table_name not in inspector.get_table_names(schema=schema):
            raise ValueError(f"Table '{schema}.{table_name}' not found.")

        columns_meta = inspector.get_columns(table_name, schema=schema)

        if not columns_meta:
            raise ValueError(f"Table '{schema}.{table_name}' has no columns.")

        prep = self.engine.dialect.identifier_preparer
        tbl = f"{prep.quote_identifier(schema)}.{prep.quote_identifier(table_name)}"

        with self.engine.connect() as conn:
            count_query = text(f'SELECT COUNT(*) FROM {tbl}')
            total_rows = conn.execute(count_query).scalar() or 0

            if total_rows == 0:
                col_names = [col["name"] for col in columns_meta]
                return ProfileReport({
                    "shape": (0, len(col_names)),
                    "columns": col_names,
                    "status": "empty_dataset",
                    "message": "The dataset contains no rows.",
                    "earliest_date": None,
                    "latest_date": None,
                    "column_summary": [],
                    "statistics": {},
                    "outliers": {},
                    "correlations": {},
                    "pii_detection": [],
                    "quality_score": {
                        "score": 100.0,
                        "missing_values": 0,
                        "duplicate_rows": 0,
                        "total_outliers": 0,
                    },
                    "worst_issues": [],
                    "top_correlations": [],
                    "anomaly_correlation": {},
                    "sparklines": {},
                    "quality_scorecard": {},
                    "insights": [],
                })

            column_summary = []
            statistics = {}
            outliers = {}
            earliest_date = None
            latest_date = None
            total_nulls = 0

            # 2. Per-column aggregated metrics
            for col in columns_meta:
                c_name = col["name"]
                qc = prep.quote_identifier(c_name)
                c_type = col["type"]
                is_num = _is_numeric_type(c_type)
                is_dt = _is_date_type(c_type)

                qc_distinct = f"{qc}::text" if _needs_text_cast(c_type) else qc

                agg_sql = text(f"""
                    SELECT 
                        COUNT(*) - COUNT({qc}) AS null_count,
                        COUNT(DISTINCT {qc_distinct}) AS unique_count
                        {f', MIN({qc}) AS min_val, MAX({qc}) AS max_val' if is_num or is_dt else ''}
                        {f', AVG({qc})::float AS mean_val, STDDEV_SAMP({qc})::float AS std_val' if is_num else ''}
                    FROM {tbl}
                """)
                res = conn.execute(agg_sql).mappings().one()

                null_count = res["null_count"]
                unique_count = res["unique_count"]
                total_nulls += null_count
                null_pct = round((null_count / total_rows) * 100, 2)

                # Classify Column Role and Cardinality
                role = "Text"
                cardinality = "High Cardinality"
                if c_name.lower() == "id":
                    role = "ID"
                elif c_name.lower().endswith("_id"):
                    role = "ID" if (unique_count / total_rows) >= 0.95 else "Foreign Key"
                elif is_num:
                    role = "Measure"
                elif unique_count <= 50:
                    role = "Category"

                if unique_count == total_rows:
                    cardinality = "Unique ID"
                elif unique_count < 50:
                    cardinality = "Category"

                column_summary.append({
                    "column": c_name,
                    "dtype": str(c_type).lower(),
                    "null_count": int(null_count),
                    "null_percent": float(null_pct),
                    "unique_count": int(unique_count),
                    "role": role,
                    "cardinality": cardinality,
                })

                if is_dt and earliest_date is None:
                    earliest_date = str(res.get("min_val"))
                    latest_date = str(res.get("max_val"))

                if is_num:
                    min_val = res.get("min_val")
                    max_val = res.get("max_val")
                    mean_val = res.get("mean_val")
                    std_val = res.get("std_val")

                    # Quantiles via percentile_cont
                    quantile_sql = text(f"""
                        SELECT 
                            percentile_cont(0.25) WITHIN GROUP (ORDER BY "{c_name}") AS q25,
                            percentile_cont(0.50) WITHIN GROUP (ORDER BY "{c_name}") AS q50,
                            percentile_cont(0.75) WITHIN GROUP (ORDER BY "{c_name}") AS q75
                        FROM {tbl}
                        WHERE "{c_name}" IS NOT NULL
                    """)
                    q_res = conn.execute(quantile_sql).mappings().one()
                    q25 = q_res["q25"] if q_res["q25"] is not None else 0.0
                    q50 = q_res["q50"] if q_res["q50"] is not None else 0.0
                    q75 = q_res["q75"] if q_res["q75"] is not None else 0.0

                    count_val = total_rows - null_count
                    statistics[c_name] = {
                        "count": int(count_val),
                        "mean": float(mean_val) if mean_val is not None else 0.0,
                        "std": float(std_val) if std_val is not None else 0.0,
                        "min": float(min_val) if min_val is not None else 0.0,
                        "25%": float(q25),
                        "50%": float(q50),
                        "75%": float(q75),
                        "max": float(max_val) if max_val is not None else 0.0,
                    }

                    # Outlier count via IQR pushdown
                    iqr = q75 - q25
                    lower_limit = q25 - (1.5 * iqr)
                    upper_limit = q75 + (1.5 * iqr)

                    outlier_sql = text(f"""
                        SELECT COUNT(*) AS out_count
                        FROM {tbl}
                        WHERE "{c_name}" < :lower_limit OR "{c_name}" > :upper_limit
                    """)
                    out_count = conn.execute(
                        outlier_sql, {"lower_limit": lower_limit, "upper_limit": upper_limit}
                    ).scalar() or 0

                    outliers[c_name] = {
                        "lower_limit": float(lower_limit),
                        "upper_limit": float(upper_limit),
                        "outlier_count": int(out_count),
                    }

            # 3. PII Detection via sampling
            pii_report = []
            for col in columns_meta:
                c_name = col["name"]
                severity = "LOW"
                reason = "No PII detected"
                if re.search(r"email|phone|ssn|address|name", c_name.lower()):
                    severity = "HIGH"
                    reason = "PII-like column name"
                else:
                    sample_sql = text(f"""
                        SELECT "{c_name}"::text AS val
                        FROM {tbl}
                        WHERE "{c_name}" IS NOT NULL
                        LIMIT :limit
                    """)
                    sample_vals = [
                        row[0] for row in conn.execute(sample_sql, {"limit": sample_rows_for_pii})
                    ]
                    for val in sample_vals:
                        if re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", str(val)):
                            severity = "HIGH"
                            reason = "Email detected"
                            break
                        if re.match(r"^\d{10}$", str(val)):
                            severity = "MEDIUM"
                            reason = "Phone number detected"
                            break

                pii_report.append({"column": c_name, "severity": severity, "reason": reason})

            group_cols_list = []
            for c in columns_meta:
                quoted_c = prep.quote_identifier(c["name"])
                if _needs_text_cast(c["type"]):
                    group_cols_list.append(f"{quoted_c}::text")
                else:
                    group_cols_list.append(quoted_c)
            group_cols = ", ".join(group_cols_list)

            dup_sql = text(f"""
                SELECT COALESCE(SUM(c - 1), 0)
                FROM (
                    SELECT COUNT(*) as c
                    FROM {tbl}
                    GROUP BY {group_cols}
                    HAVING COUNT(*) > 1
                ) sub
            """)
            duplicate_rows = int(conn.execute(dup_sql).scalar() or 0)

            total_outliers = sum(item["outlier_count"] for item in outliers.values())

            # 5. Quality Score computation
            score = 100
            if total_nulls > 0:
                score -= 20
            if duplicate_rows > 0:
                score -= 10
            if total_outliers > 0:
                score -= 10
            if any(p["severity"] != "LOW" for p in pii_report):
                score -= 10

            quality_score = {
                "score": max(score, 0),
                "missing_values": int(total_nulls),
                "duplicate_rows": duplicate_rows,
                "total_outliers": int(total_outliers),
            }

            # 6. Ranked Worst Issues
            worst_issues = []
            for col in columns_meta:
                c_name = col["name"]
                col_score = 0
                problems = []

                c_summary = next(item for item in column_summary if item["column"] == c_name)
                if c_summary["null_count"] > 0:
                    problems.append(f"{c_summary['null_count']} missing values")
                    col_score += c_summary["null_count"]

                if c_name in outliers and outliers[c_name]["outlier_count"] > 0:
                    out_cnt = outliers[c_name]["outlier_count"]
                    problems.append(f"{out_cnt} outliers")
                    col_score += out_cnt

                pii_info = next((p for p in pii_report if p["column"] == c_name), None)
                if pii_info and pii_info["severity"] != "LOW":
                    problems.append(f"Possible PII: {pii_info['reason']}")
                    col_score += 100

                sev = "High" if col_score >= 100 else ("Medium" if col_score > 0 else "Low")
                worst_issues.append({
                    "column": c_name,
                    "problems": ", ".join(problems) if problems else "No major issues",
                    "score": col_score,
                    "severity": sev,
                })

            worst_issues.sort(key=lambda x: x["score"], reverse=True)
            for idx, issue in enumerate(worst_issues, start=1):
                issue["rank"] = idx

            return ProfileReport({
                "shape": (int(total_rows), len(columns_meta)),
                "columns": [col["name"] for col in columns_meta],
                "earliest_date": earliest_date,
                "latest_date": latest_date,
                "column_summary": column_summary,
                "statistics": statistics,
                "outliers": outliers,
                "correlations": {},
                "pii_detection": pii_report,
                "quality_score": quality_score,
                "worst_issues": worst_issues,
                "top_correlations": [],
                "anomaly_correlation": {},
                "sparklines": {},
                "insights": [],
                "quality_scorecard": {},
            })