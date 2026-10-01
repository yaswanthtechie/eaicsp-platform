select
    snapshot_date::date as snapshot_date,
    sku_id::varchar(50) as sku_id,
    warehouse_id::varchar(20) as warehouse_id,
    quantity_on_hand::integer as quantity_on_hand,
    source_batch::varchar(100) as source_batch,
    run_id::bigint as run_id,
    pipeline_version::varchar(20) as pipeline_version,
    loaded_at,
    updated_at
from {{ source('etl', 'inventory_snapshot') }}
