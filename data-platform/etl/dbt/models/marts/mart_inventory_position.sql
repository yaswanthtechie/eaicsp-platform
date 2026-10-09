with ranked as (
    select
        snapshot_date,
        sku_id,
        warehouse_id,
        quantity_on_hand,
        row_number() over (
            partition by sku_id, warehouse_id
            order by snapshot_date desc, updated_at desc
        ) as rn
    from {{ ref('stg_inventory_snapshot') }}
)
select
    snapshot_date,
    sku_id,
    warehouse_id,
    quantity_on_hand
from ranked
where rn = 1
