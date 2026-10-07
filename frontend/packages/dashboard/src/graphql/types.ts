export interface DashboardQueryData {
  dashboard: {
    kpis: {
      totalSkus: number;
      totalUnits: number;
      reorderItems: number;
      alerts: number;
    };

    inventory: {
      sku_id: string;
      product_name: string;
      category: string;
      warehouse_id: string;
      quantity_on_hand: number;
      reorder_point: number;
      needs_reorder: boolean;
      avg_daily_demand: number;
    }[];

    forecast: {
      date: string;
      predicted: number;
      lower_bound: number;
      upper_bound: number;
      actual?: number;
    }[];
    
    forecastAccuracy: {
      date: string;
      accuracy: number;
      target: number;
    }[];
    inventoryHealth: {
      warehouse_id: string;
      total_skus: number;
      low_stock_count: number;
      out_of_stock_count: number;
    }[];
    supplierRisk: {
      supplier: string;
      risk_score: number;
      confidence: number;
      sentiment_breakdown: {
        positive: number;
        negative: number;
        neutral: number;
      };
    }[];
    shipmentStatus: {
      total: number;
      pending: number;
      delivered: number;
      in_transit: number;
      delayed: number;
      cancelled: number;
    };
  };
}