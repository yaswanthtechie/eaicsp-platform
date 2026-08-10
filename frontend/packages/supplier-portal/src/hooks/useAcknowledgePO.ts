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
          po_number: poNumber,
        },
      });

      return {
        queued: true,
      };
    }

    /*
     * Online:
     * Execute the existing GraphQL mutation.
     */
    await acknowledgePurchaseOrder({
      variables: {
        po_number: poNumber,
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