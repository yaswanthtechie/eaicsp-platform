import math


def compare_reports(pandas_report: dict, sql_report: dict, rel_tol: float = 1e-6) -> list[str]:
    """Return a list of mismatches between pandas and pushdown reports. Empty = parity."""
    mismatches = []

    if tuple(pandas_report["shape"]) != tuple(sql_report["shape"]):
        mismatches.append(f"shape: pandas={pandas_report['shape']} sql={sql_report['shape']}")

    p_cols = {c["column"]: c for c in pandas_report["column_summary"]}
    s_cols = {c["column"]: c for c in sql_report["column_summary"]}
    for col, p in p_cols.items():
        s = s_cols.get(col)
        if s is None:
            mismatches.append(f"{col}: missing from SQL report")
            continue
        for key in ("null_count", "unique_count"):
            if p[key] != s[key]:
                mismatches.append(f"{col}.{key}: pandas={p[key]} sql={s[key]}")

    for col, p in pandas_report["statistics"].items():
        s = sql_report["statistics"].get(col)
        if s is None:
            mismatches.append(f"{col}: no SQL statistics")
            continue
        for key in ("count", "mean", "std", "min", "25%", "50%", "75%", "max"):
            if not math.isclose(float(p[key]), float(s[key]), rel_tol=rel_tol, abs_tol=1e-9):
                mismatches.append(f"{col}.{key}: pandas={p[key]} sql={s[key]}")

    for col, p in pandas_report["outliers"].items():
        s = sql_report["outliers"].get(col, {})
        if p.get("outlier_count") != s.get("outlier_count"):
            mismatches.append(
                f"{col}.outlier_count: pandas={p.get('outlier_count')} sql={s.get('outlier_count')}"
            )
    return mismatches