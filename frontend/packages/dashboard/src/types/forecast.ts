export interface ForecastPoint {
  date: string // "2026-08-01"
  predicted: number
  lower_bound: number // confidence band bottom
  upper_bound: number // confidence band top
  actual?: number // only for past dates
}

export interface InventoryItem {
  sku_id: string
  product_name: string
  warehouse_id: string
  quantity_on_hand: number
  reorder_point: number
  needs_reorder: boolean
}