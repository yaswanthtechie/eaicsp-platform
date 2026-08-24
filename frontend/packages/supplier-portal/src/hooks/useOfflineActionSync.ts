import { useCallback } from "react";
import { useApolloClient } from "@apollo/client";

import {
  ACKNOWLEDGE_PO,
  SUBMIT_INVOICE,
} from "../graphql/mutations";
import { useOfflineSync } from "./useOfflineSync";

export const useOfflineActionSync = (
  onSyncComplete?: (count: number) => void
) => {
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

        case "SUBMIT_INVOICE": {
          const invoiceNumber = payload.invoiceNumber;
          const poReference = payload.poReference;
          const amount = payload.amount;
          const date = payload.date;

          if (
            typeof invoiceNumber !== "string" ||
            typeof poReference !== "string" ||
            typeof amount !== "number" ||
            typeof date !== "string"
          ) {
            throw new Error(
              "Invalid invoice payload."
            );
          }

          await client.mutate({
            mutation: SUBMIT_INVOICE,
            variables: {
              invoiceNumber,
              poReference,
              amount,
              date,
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

  useOfflineSync(handleSync, onSyncComplete);
};