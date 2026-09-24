"""Benchmark monthly partition pruning with production-shaped benchmark data."""
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))

from sqlalchemy import text
from database import get_engine

RESULT_PATH = REPO_ROOT / "docs" / "partitioning_benchmark.json"

REPEATS = 5
BENCHMARK_ROWS = 1_000_000
BENCHMARK_MONTHS = 84


def month_start(d):
    return date(d.year, d.month, 1)


def add_months(d, months):
    total = d.year * 12 + (d.month - 1) + months
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def next_month(d):
    return add_months(d, 1)


def timed(conn, sql, params):
    start = time.perf_counter()
    conn.execute(text(sql), params).scalar()
    return time.perf_counter() - start


def populate_benchmark_table(conn, table_name):
    """Create a large dataset distributed across multiple months."""
    source_count = conn.execute(
        text("SELECT COUNT(*) FROM sales_fact")
    ).scalar()

    if not source_count:
        raise RuntimeError("sales_fact contains no rows")

    multiplier = (
        BENCHMARK_ROWS + source_count - 1
    ) // source_count

    conn.execute(
        text(
            f"""
            INSERT INTO {table_name}
            (
                id,
                date,
                sku_id,
                warehouse_id,
                quantity_sold,
                unit_price,
                source_batch,
                run_id,
                pipeline_version,
                loaded_at,
                updated_at
            )
            SELECT
                sf.id
                    + ((g.multiplier - 1)::bigint * 1000000000::bigint)
                    AS id,

                (
                    sf.date
                    + ((g.multiplier - 1) * INTERVAL '1 month')
                )::date AS date,

                sf.sku_id,
                sf.warehouse_id,
                sf.quantity_sold,
                sf.unit_price,
                sf.source_batch,
                sf.run_id,
                sf.pipeline_version,
                sf.loaded_at,
                sf.updated_at

            FROM sales_fact sf
            CROSS JOIN generate_series(
                1,
                :multiplier
            ) AS g(multiplier)

            LIMIT :target_rows
            """
        ),
        {
            "multiplier": multiplier,
            "target_rows": BENCHMARK_ROWS,
        },
    )


def main():
    engine = get_engine()

    with engine.begin() as c:
        bounds = c.execute(
            text(
                "SELECT MIN(date), MAX(date), COUNT(*) "
                "FROM sales_fact"
            )
        ).fetchone()

        if not bounds or bounds[0] is None:
            raise RuntimeError(
                "sales_fact contains no rows; "
                "cannot run partition benchmark"
            )

        min_date, max_date, row_count = bounds

        benchmark_start = month_start(min_date)
        benchmark_end = add_months(
            benchmark_start,
            BENCHMARK_MONTHS,
        )

        c.execute(
            text(
                "DROP TABLE IF EXISTS "
                "sales_partition_bench CASCADE"
            )
        )

        c.execute(
            text(
                "DROP TABLE IF EXISTS "
                "sales_partitioned_bench CASCADE"
            )
        )

        # Unpartitioned benchmark table.
        c.execute(
            text(
                """
                CREATE TABLE sales_partition_bench
                AS SELECT * FROM sales_fact WITH NO DATA
                """
            )
        )

        populate_benchmark_table(
            c,
            "sales_partition_bench",
        )

        # Partitioned benchmark table.
        c.execute(
            text(
                """
                CREATE TABLE sales_partitioned_bench
                (LIKE sales_fact INCLUDING DEFAULTS)
                PARTITION BY RANGE (date)
                """
            )
        )

        cursor = benchmark_start
        partitions = []

        while cursor < benchmark_end:
            nxt = next_month(cursor)

            name = (
                f"sales_partitioned_bench_"
                f"{cursor:%Y_%m}"
            )

            c.execute(
                text(
                    f"""
                    CREATE TABLE {name}
                    PARTITION OF sales_partitioned_bench
                    FOR VALUES FROM ('{cursor}')
                    TO ('{nxt}')
                    """
                )
            )

            partitions.append(name)
            cursor = nxt

        # Catch rows outside the configured monthly range.
        c.execute(
            text(
                """
                CREATE TABLE
                sales_partitioned_bench_default
                PARTITION OF sales_partitioned_bench
                DEFAULT
                """
            )
        )

        populate_benchmark_table(
            c,
            "sales_partitioned_bench",
        )

        # Update PostgreSQL statistics.
        c.execute(
            text("ANALYZE sales_partition_bench")
        )

        c.execute(
            text("ANALYZE sales_partitioned_bench")
        )

    # Query only the first month.
    query_month = benchmark_start
    query_end = next_month(query_month)

    params = {
        "start": query_month,
        "end": query_end,
    }

    sql = (
        "SELECT COUNT(*) "
        "FROM {table} "
        "WHERE date >= :start "
        "AND date < :end"
    )

    with engine.connect() as c:
        # Warm both paths.
        c.execute(
            text(
                sql.format(
                    table="sales_partition_bench"
                )
            ),
            params,
        ).scalar()

        c.execute(
            text(
                sql.format(
                    table="sales_partitioned_bench"
                )
            ),
            params,
        ).scalar()

        before_times = []
        after_times = []

        for _ in range(REPEATS):
            before_times.append(
                timed(
                    c,
                    sql.format(
                        table="sales_partition_bench"
                    ),
                    params,
                )
            )

            after_times.append(
                timed(
                    c,
                    sql.format(
                        table="sales_partitioned_bench"
                    ),
                    params,
                )
            )

        plan_rows = c.execute(
            text(
                "EXPLAIN "
                "(ANALYZE, COSTS OFF, SUMMARY OFF) "
                + sql.format(
                    table="sales_partitioned_bench"
                )
            ),
            params,
        ).fetchall()

    before = statistics.median(before_times)
    after = statistics.median(after_times)

    speedup = before / after if after else None

    plan = [row[0] for row in plan_rows]

    scanned = [
        name
        for name in partitions
        if any(name in line for line in plan)
    ]

    expected_partition = (
        f"sales_partitioned_bench_"
        f"{query_month:%Y_%m}"
    )

    pruned = (
        len(scanned) == 1
        and scanned[0] == expected_partition
    )

    result = {
        "measured_at": date.today().isoformat(),
        "source_rows": row_count,
        "benchmark_rows": BENCHMARK_ROWS,
        "benchmark_months": BENCHMARK_MONTHS,
        "production_data_range": {
            "min": str(min_date),
            "max": str(max_date),
        },
        "benchmark_data_range": {
            "start": str(benchmark_start),
            "end": str(
                add_months(
                    benchmark_start,
                    BENCHMARK_MONTHS - 1,
                )
            ),
        },
        "query_range": {
            "start": str(query_month),
            "end": str(query_end),
        },
        "repeats": REPEATS,
        "before_median_seconds": before,
        "after_median_seconds": after,
        "speedup_x": speedup,
        "partition_pruning": pruned,
        "scanned_partitions": scanned,
        "plan": plan,
    }

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_PATH.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    # Cleanup temporary benchmark tables.
    with engine.begin() as c:
        c.execute(
            text(
                "DROP TABLE IF EXISTS "
                "sales_partition_bench CASCADE"
            )
        )

        c.execute(
            text(
                "DROP TABLE IF EXISTS "
                "sales_partitioned_bench CASCADE"
            )
        )

    print(json.dumps(result, indent=2))

    if not pruned:
        raise SystemExit(
            "FAIL: partition pruning was not proven"
        )

    if speedup is None or speedup <= 1.0:
        raise SystemExit(
            "FAIL: this environment did not demonstrate "
            "a measurable partition speedup"
        )

    print(
        f"PASS: median date-range speedup = "
        f"{speedup:.2f}x; "
        f"result recorded at {RESULT_PATH}"
    )


if __name__ == "__main__":
    main()