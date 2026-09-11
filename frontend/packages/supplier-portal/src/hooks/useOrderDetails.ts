import { usePurchaseOrders } from "./usePurchaseOrders";
import { ORDER_DETAILS_PAGE_SIZE } from "../constants/pagination";

export const useOrderDetails = () => {
  return usePurchaseOrders({
    first: ORDER_DETAILS_PAGE_SIZE,
    after: null,
  });
};