import { gql } from "@apollo/client";

export const GET_DASHBOARD = gql`
  query GetDashboard {
    dashboard {
      kpis {
        totalSkus
        totalUnits
        reorderItems
        alerts
      }

      inventory {
        sku_id
        product_name
        category
        warehouse_id
        quantity_on_hand
        reorder_point
        needs_reorder
        avg_daily_demand
      }

      forecast {
        date
        predicted
        lower_bound
        upper_bound
        actual
      }

      forecastAccuracy {
        date
        accuracy
        target
      }

      inventoryHealth {
        warehouse_id
        total_skus
        low_stock_count
        out_of_stock_count
      }

      supplierRisk {
        supplier
        risk_score
        confidence
        sentiment_breakdown {
          positive
          negative
          neutral
        }
      }

      shipmentStatus {
        total
        pending
        delivered
        in_transit
        delayed
        cancelled
      }
    }
  }
`;