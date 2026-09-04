import { gql } from "@apollo/client";

export const GET_PURCHASE_ORDERS = gql`
  query GetPurchaseOrders(
    $first: Int!
    $after: String
    $status: String
    $poNumber: String
    $minAmount: Int
    $maxAmount: Int
    $startDate: String
    $endDate: String
  ) {
    purchaseOrders(
      first: $first
      after: $after
      status: $status
      poNumber: $poNumber
      minAmount: $minAmount
      maxAmount: $maxAmount
      startDate: $startDate
      endDate: $endDate
    ) {
      edges {
        cursor
        node {
          po_number
          supplier_id
          status
          total_amount
          expected_delivery

          items {
            sku
            product_name
            quantity
            unit_price
          }
        }
      }

      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
`;