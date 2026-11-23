import {
  getAuthSession,
  refreshAuthSession,
} from "./auth";

import { supplierScorecardResponse } from "../mocks/supplierScorecardResponses";

export interface SupplierPerformance {
  supplier_id: string;
  supplier_name: string | null;
  received_po_count: number;
  on_time_po_count: number;
  on_time_delivery_percent: number | null;
  total_po_count: number;
  open_po_count: number;
  late_po_count: number;
}

export interface ClientRiskFeatures {
  quality_incidents_12m: number;
  delay_incidents_12m: number;
  dispute_incidents_12m: number;
  other_incidents_12m: number;
  days_since_last_incident: number | null;
  on_time_delivery_pct: number | null;
  on_time_delivery_missing: boolean;
}

export interface SupplierRiskResponse {
  supplier_id: string;
  score: number | null;
  tier: "Low" | "Medium" | "High" | "Critical" | null;
  top_reasons: string[];
  client_risk_features: ClientRiskFeatures | null;
}

export interface SupplierScorecardRow {
  supplier_id: string;
  supplier_name: string;
  on_time_delivery_percent: number | null;
  risk: SupplierRiskResponse | null;
  risk_error: string | null;
}

const API_TIMEOUT_MS = 30000;

const USE_MOCK_SUPPLIER_SCORECARD =
  import.meta.env.DEV &&
  import.meta.env.VITE_USE_MOCK_SUPPLIER_SCORECARD === "true";

async function fetchJson<T>(path: string): Promise<T> {
  const session = getAuthSession();

  if (!session?.access_token) {
    throw new Error("Your session is unavailable. Please sign in again.");
  }

  const controller = new AbortController();

  const timeout = window.setTimeout(
    () => controller.abort(),
    API_TIMEOUT_MS,
  );

  // Send the request using the current access token.
  const sendRequest = (accessToken: string) =>
    fetch(path, {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      signal: controller.signal,
    });

  try {
    let response = await sendRequest(session.access_token);

    // If unauthorized, refresh the token and retry once.
    if (response.status === 401) {
      const refreshedSession = await refreshAuthSession();

      response = await sendRequest(refreshedSession.access_token);
    }

    if (!response.ok) {
      throw new Error(`Request failed (${response.status}).`);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out.", { cause: error });
    }

    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function fetchSupplierPerformance(): Promise<
  SupplierPerformance[]
> {
  return fetchJson<SupplierPerformance[]>(
    "/api/v1/inventory/suppliers/performance",
  );
}

export async function fetchSupplierRisk(
  supplierId: string,
): Promise<SupplierRiskResponse> {
  return fetchJson<SupplierRiskResponse>(
    `/api/v1/suppliers/${encodeURIComponent(supplierId)}/risk-score`,
  );
}

export async function fetchSupplierScorecard(): Promise<
  SupplierScorecardRow[]
> {
  // Return mock data when enabled in development.
  if (USE_MOCK_SUPPLIER_SCORECARD) {
    return supplierScorecardResponse;
  }
  const suppliers = await fetchSupplierPerformance();

  return Promise.all(
    suppliers.map(async (supplier) => {
      try {
        const risk = await fetchSupplierRisk(supplier.supplier_id);

        return {
          supplier_id: supplier.supplier_id,
          supplier_name: supplier.supplier_name?.trim() || supplier.supplier_id,
          on_time_delivery_percent: supplier.on_time_delivery_percent,
          risk,
          risk_error: null,
        };
      } catch (error) {
        return {
          supplier_id: supplier.supplier_id,
          supplier_name: supplier.supplier_name?.trim() || supplier.supplier_id,
          on_time_delivery_percent: supplier.on_time_delivery_percent,
          risk: null,
          risk_error: error instanceof Error ? error.message : "Risk data unavailable.",
        };
      }
    }),
  );
}
