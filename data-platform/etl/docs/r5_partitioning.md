# R5 Stretch: `sales_fact` Date-Range Partitioning

## Design

At production scale, partition `sales_fact` by the `date` column using PostgreSQL range partitions. A practical starting point is one partition per calendar year, with the option to move to monthly partitions if yearly partitions become too large.

```text
sales_fact (partitioned by RANGE(date))
├── sales_fact_2024  VALUES FROM ('2024-01-01') TO ('2025-01-01')
├── sales_fact_2025  VALUES FROM ('2025-01-01') TO ('2026-01-01')
├── sales_fact_2026  VALUES FROM ('2026-01-01') TO ('2027-01-01')
└── sales_fact_default / future partition as an operational safety net
```

## Why date range partitioning?

- Most sales queries naturally filter by date or date ranges, so PostgreSQL can use **partition pruning** and avoid scanning unrelated periods.
- Older partitions can be archived, backed up, or retained according to different policies without moving the whole table.
- Indexes can be maintained per partition, reducing the size and maintenance cost of each individual index.
- Loading and deleting data for a bounded period can target only the affected partition(s).
- Partition sizes remain manageable as `sales_fact` grows over multiple years.

## Important production considerations

1. Keep the partition key aligned with the common query/load time dimension (`date`).
2. Pre-create the next partition before data for that period arrives, or use an operational process to create it automatically.
3. Keep the same required indexes/constraints on every partition.
4. Monitor partition sizes. If yearly partitions become too large for the workload, move to monthly partitions.
5. Test the interaction between partitioning and the existing unique business key `(date, sku_id, warehouse_id)` before production rollout.
6. Keep partition management separate from the R5 ETL logic; this round only requires the architecture sketch.

## PostgreSQL sketch

```sql
CREATE TABLE sales_fact (
    date DATE NOT NULL,
    sku_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(20) NOT NULL,
    quantity_sold INTEGER,
    unit_price NUMERIC(12,2),
    source_batch VARCHAR(255),
    run_id BIGINT,
    loaded_at TIMESTAMP,
    updated_at TIMESTAMP
) PARTITION BY RANGE (date);

CREATE TABLE sales_fact_2026
    PARTITION OF sales_fact
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
```

This is a design sketch only; no production partition migration is required for Round 5.
