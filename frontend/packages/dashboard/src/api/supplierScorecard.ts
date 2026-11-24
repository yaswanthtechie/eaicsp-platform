import {
  getAuthSession,
  refreshAuthSession,
} from "./auth";
import type { AuthSession } from "./auth";
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
  top_reasons?: string[];
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
const RISK_API_TIMEOUT_MS = 2000;
const MAX_CONCURRENT_RISK_REQUESTS = 5;

function isMockSupplierScorecard(): boolean {
  return (
    import.meta.env.DEV &&
    import.meta.env.VITE_USE_MOCK_SUPPLIER_SCORECARD === "true"
  );
}

async function fetchJson<T>(
  path: string,
  timeoutMs = API_TIMEOUT_MS,
   onAuthSessionRefreshed?: (session: AuthSession) => void,
) : Promise<T> {
  
  const session = getAuthSession();

  if (!session?.access_token) {
    throw new Error("Your session is unavailable. Please sign in again.");
  }

  const controller = new AbortController();

  const timeout = window.setTimeout(
    () => controller.abort(),
    timeoutMs,
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
      onAuthSessionRefreshed?.(refreshedSession);

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

export async function fetchSupplierPerformance(
  onAuthSessionRefreshed?: (session: AuthSession) => void,
): Promise<SupplierPerformance[]> {
  return fetchJson<SupplierPerformance[]>(
    "/api/v1/inventory/suppliers/performance",
    API_TIMEOUT_MS,
    onAuthSessionRefreshed,
  );
}

export async function fetchSupplierRisk(
  supplierId: string,
  onAuthSessionRefreshed?: (session: AuthSession) => void,
): Promise<SupplierRiskResponse> {
  return fetchJson<SupplierRiskResponse>(
    `/api/v1/suppliers/${encodeURIComponent(supplierId)}/risk-score`,
    RISK_API_TIMEOUT_MS,
    onAuthSessionRefreshed,
  );
}

export async function fetchSupplierScorecard(
  onAuthSessionRefreshed?: (session: AuthSession) => void,
): Promise<
  SupplierScorecardRow[]
> {
  // Return mock data when enabled in development.
  if (isMockSupplierScorecard()) {
    return supplierScorecardResponse;
  }
  
  // The performance endpoint is the only supplier list, so without it
  // there is nothing to fetch risk for. Say exactly what is missing.
  let suppliers: SupplierPerformance[];

  try {
    suppliers = await fetchSupplierPerformance(onAuthSessionRefreshed);
  } catch (error) {
    const reason = error instanceof Error ? error.message : "no response";

    throw new Error(
      `Supplier list and on-time data are unavailable (${reason}). ` +
        "Risk scores cannot be loaded without the supplier list.",
      { cause: error },
    );
  }

  const results: SupplierScorecardRow[] = new Array(suppliers.length);
  let nextIndex = 0;

  // Each worker processes one supplier at a time.
  async function processSuppliers(): Promise<void> {
    while (nextIndex < suppliers.length) {
      const index = nextIndex++;
      const supplier = suppliers[index];
      try {
        const risk = await fetchSupplierRisk(
          supplier.supplier_id,
          onAuthSessionRefreshed,
        );

        results[index] = {
          supplier_id: supplier.supplier_id,
          supplier_name: supplier.supplier_name?.trim() || supplier.supplier_id,
          on_time_delivery_percent: supplier.on_time_delivery_percent,
          risk,
          risk_error: null,
        };
      } catch (error) {
        results[index] = {
          supplier_id: supplier.supplier_id,
          supplier_name: supplier.supplier_name?.trim() || supplier.supplier_id,
          on_time_delivery_percent: supplier.on_time_delivery_percent,
          risk: null,
          risk_error: error instanceof Error ? error.message : "Risk data unavailable.",
        };
      }
    }
  }
  const workerCount = Math.min(
    MAX_CONCURRENT_RISK_REQUESTS,
    suppliers.length,
  );

  await Promise.all(
    Array.from({ length: workerCount }, () => processSuppliers()),
  );

  return results;
}
