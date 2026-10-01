select
    date::date as sale_date,
    sku_id::varchar(50) as sku_id,
    warehouse_id::varchar(20) as warehouse_id,
    quantity_sold::integer as quantity_sold,
    unit_price::numeric(12,2) as unit_price,
    source_batch::varchar(100) as source_batch,
    run_id::bigint as run_id,
    pipeline_version::varchar(20) as pipeline_version,
    loaded_at,
    updated_at
from {{ source('etl', 'sales_fact') }}
