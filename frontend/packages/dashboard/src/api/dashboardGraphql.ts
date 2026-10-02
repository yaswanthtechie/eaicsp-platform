import { useQuery } from "@apollo/client/react";
import { GET_DASHBOARD } from "../graphql/queries";
import type { DashboardQueryData } from "../graphql/types";

export function useDashboardData() {
  return useQuery<DashboardQueryData>(GET_DASHBOARD);
}