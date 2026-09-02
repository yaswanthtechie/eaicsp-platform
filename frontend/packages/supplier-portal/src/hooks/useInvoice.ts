import { useMutation } from "@apollo/client";

import { SUBMIT_INVOICE } from "../graphql/mutations";
import { addOfflineAction } from "../utils/offlineQueue";
import { usePurchaseOrders } from "./usePurchaseOrders";

import { INVOICE_PAGE_SIZE } from "../constants/pagination";

import type { PurchaseOrder } from "../types/po";
import type { PurchaseOrderEdge } from "../types/graphql";

export const useInvoice = () => {
  const purchaseOrders = usePurchaseOrders({
    first: INVOICE_PAGE_SIZE,
    after: null,
  });

  const [submitInvoice, mutationState] =
    useMutation(SUBMIT_INVOICE);

  const orders: PurchaseOrder[] =
    purchaseOrders.data?.purchaseOrders?.edges?.map(
      (edge: PurchaseOrderEdge) => edge.node
    ) || [];

  const acknowledgedPOs = orders.filter(
    (po) => po.status === "ACKNOWLEDGED"
  );

  const submitInvoiceWithOfflineSupport = async (
    invoiceNumber: string,
    poReference: string,
    amount: number,
    date: string
  ) => {
    if (!navigator.onLine) {
      addOfflineAction({
        type: "SUBMIT_INVOICE",
        payload: {
          invoiceNumber,
          poReference,
          amount,
          date,
        },
      });

      return {
        queued: true,
      };
    }

    await submitInvoice({
      variables: {
        invoiceNumber,
        poReference,
        amount,
        date,
      },
    });

    return {
      queued: false,
    };
  };

  return {
    submitInvoice,
    submitInvoiceWithOfflineSupport,
    acknowledgedPOs,
    ...mutationState,
    ...purchaseOrders,
  };
};