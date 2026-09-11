import { useMutation } from "@apollo/client";

import { ACKNOWLEDGE_PO } from "../graphql/mutations";
import { addOfflineAction } from "../utils/offlineQueue";

export const useAcknowledgePO = () => {
  const [
    acknowledgePurchaseOrder,
    mutationState,
  ] = useMutation(ACKNOWLEDGE_PO);

  const acknowledgePO = async (
    poNumber: string
  ) => {
    /*
     * Offline:
     * Store the acknowledgement locally.
     */
    if (!navigator.onLine) {
      addOfflineAction({
        type: "ACKNOWLEDGE_PO",
        payload: {
          poNumber,
        },
      });

      return {
        queued: true,
      };
    }

    /*
     * Online:
     * Execute the GraphQL mutation with optimistic UI.
     */
    await acknowledgePurchaseOrder({
      variables: {
        poNumber,
      },
      optimisticResponse: {
        acknowledgePurchaseOrder: {
          __typename: "PurchaseOrder",
          poNumber,
          status: "ACKNOWLEDGED",
        },
      },
    });

    return {
      queued: false,
    };
  };

  return {
    acknowledgePurchaseOrder,
    acknowledgePO,
    ...mutationState,
  };
};