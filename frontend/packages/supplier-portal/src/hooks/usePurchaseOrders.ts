import { useQuery } from "@apollo/client";
import { GET_PURCHASE_ORDERS } from "../graphql/queries";
import { POLLING_INTERVAL } from "../constants/pagination";

interface PurchaseOrdersVariables {
  first: number;
  after?: string | null;
  status?: string;
  poNumber?: string;
  minAmount?: number;
  maxAmount?: number;
  startDate?: string;
  endDate?: string;
}

export function usePurchaseOrders(
  variables: PurchaseOrdersVariables
) {
  return useQuery(GET_PURCHASE_ORDERS, {
    variables,
    notifyOnNetworkStatusChange: true,
    pollInterval: POLLING_INTERVAL,
    errorPolicy: "all",
  });
}