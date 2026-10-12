select *
from {{ ref('mart_daily_sales_by_warehouse') }}
where units_sold < 0
   or sales_amount < 0
