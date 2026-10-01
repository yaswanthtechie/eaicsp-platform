select
    sale_date,
    warehouse_id,
    count(*) as sales_rows,
    sum(quantity_sold) as units_sold,
    sum(quantity_sold * unit_price) as sales_amount
from {{ ref('stg_sales_fact') }}
group by sale_date, warehouse_id
