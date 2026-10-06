import { useQuery } from "@apollo/client/react";
import { GET_DASHBOARD } from "../graphql/queries";
import type { DashboardQueryData } from "../graphql/types";

export function useDashboardData() {
  const result = useQuery<DashboardQueryData>(GET_DASHBOARD);

  // If a refetch fails, Apollo clears `data` but keeps `previousData`.
  // Keep showing the last good data so a failed refresh never blanks
  // a dashboard the user is already looking at.
  return {
    ...result,
    data: result.data ?? result.previousData,
  };
}