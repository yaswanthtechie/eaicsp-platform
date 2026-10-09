select
    shipment_date,
    warehouse_id,
    count(*) as shipment_rows,
    sum(shipped_quantity) as units_shipped
from {{ ref('stg_shipments_fact') }}
group by shipment_date, warehouse_id
