import { gql } from "@apollo/client";

export const GET_PURCHASE_ORDERS = gql`
query GetPurchaseOrders {
  purchaseOrders {
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
`;