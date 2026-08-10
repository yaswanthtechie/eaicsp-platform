import { useCallback } from "react";
import { useApolloClient } from "@apollo/client";

import { ACKNOWLEDGE_PO } from "../graphql/mutations";
import { useOfflineSync } from "./useOfflineSync";

export const useOfflineActionSync = () => {
  const client = useApolloClient();

  const handleSync = useCallback(
    async (
      type: string,
      payload: Record<string, unknown>
    ) => {
      switch (type) {
        case "ACKNOWLEDGE_PO": {
          const poNumber = payload.po_number;

          if (typeof poNumber !== "string") {
            throw new Error(
              "Invalid Purchase Order number."
            );
          }

          await client.mutate({
            mutation: ACKNOWLEDGE_PO,
            variables: {
              po_number: poNumber,
            },
          });

          break;
        }

        default:
          throw new Error(
            `Unsupported offline action: ${type}`
          );
      }
    },
    [client]
  );

  useOfflineSync(handleSync);
};