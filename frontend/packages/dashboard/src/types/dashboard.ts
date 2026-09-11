export interface ForecastAccuracyPoint {
  date: string;
  accuracy: number;
  target: number;
}

export interface InventoryHealthItem {
  warehouse_id: string;
  total_skus: number;
  low_stock_count: number;
  out_of_stock_count: number;
}

export interface SupplierRiskItem {
  supplier: string;
  risk_score: number;
  confidence: number;
  sentiment_breakdown: {
    positive: number;
    negative: number;
    neutral: number;
  };
}

export interface ShipmentStatus {
  total: number;
  pending: number;
  delivered: number;
  in_transit: number;
  delayed: number;
  cancelled: number;
}