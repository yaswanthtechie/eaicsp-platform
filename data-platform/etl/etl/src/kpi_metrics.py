"""Refresh dashboard KPI snapshots from the contracted ClickHouse views."""

from datetime import date, datetime, timezone

METRICS = {
    "stockout_count": {
        "view": "kpi_stockouts_by_warehouse",
        "numerator": "stockout_count",
        "denominator": None,
    },
    "open_pos": {
        "view": "kpi_open_pos_by_status",
        "numerator": "open_po_count",
        "denominator": None,
    },
    "fill_rate": {
        "view": "kpi_fill_rate_by_warehouse",
        "numerator": "lines_fulfilled",
        "denominator": "total_lines_ordered",
    },
    "on_time_delivery_pct": {
        "view": "kpi_on_time_delivery_by_warehouse",
        "numerator": "delivered_on_time",
        "denominator": "total_shipments",
    },
}

COLUMNS = (
    "metric_date",
    "metric_name",
    "warehouse_id",
    "category",
    "value",
    "computed_at",
    "version",
)


def refresh_kpi_metrics(client, database, metric_date=None):
    """Write warehouse-level and overall KPI values into kpi_metrics."""
    if metric_date is None:
        metric_date = datetime.now(timezone.utc).date()

    if isinstance(metric_date, str):
        metric_date = date.fromisoformat(metric_date)

    if not database.replace("_", "").isalnum() or not (
        database[0].isalpha() or database[0] == "_"
    ):
        raise ValueError(f"Invalid ClickHouse database: {database!r}")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []

    for metric_name, definition in METRICS.items():
        numerator = definition["numerator"]
        denominator = definition["denominator"]
        view = definition["view"]

        select_columns = (
            f"sum({numerator}) AS numerator"
            + (
                f", sum({denominator}) AS denominator"
                if denominator is not None
                else ""
            )
        )

        query = (
            f"SELECT warehouse_id, {select_columns} "
            f"FROM `{database}`.`{view}` "
            "GROUP BY warehouse_id ORDER BY warehouse_id"
        )

        result = client.query(query)
        total_numerator = 0
        total_denominator = 0
        has_data = False

        for record in result.result_rows:
            warehouse_id = record[0]
            numerator_value = record[1]
            denominator_value = record[2] if denominator else None

            if denominator is not None:
                if not denominator_value:
                    continue
                value = round(
                    100.0 * numerator_value / denominator_value, 2
                )
                total_denominator += denominator_value
            else:
                value = float(numerator_value)

            total_numerator += numerator_value
            has_data = True

            rows.append((
                metric_date, metric_name, warehouse_id, "",
                value, now, now,
            ))

        if has_data and (denominator is None or total_denominator > 0):
            overall_value = (
                round(100.0 * total_numerator / total_denominator, 2)
                if denominator is not None
                else float(total_numerator)
            )
            rows.append((
                metric_date, metric_name, "", "",
                overall_value, now, now,
            ))

    if rows:
        client.insert(
            "kpi_metrics",
            rows,
            column_names=list(COLUMNS),
            database=database,
        )

    return len(rows)
