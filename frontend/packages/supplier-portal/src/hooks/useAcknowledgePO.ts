import { useMutation } from "@apollo/client";

import { ACKNOWLEDGE_PO } from "../graphql/mutations";

export const useAcknowledgePO = () => {
  const [acknowledgePurchaseOrder, mutationState] =
    useMutation(ACKNOWLEDGE_PO);

  return {
    acknowledgePurchaseOrder,
    ...mutationState,
  };
};