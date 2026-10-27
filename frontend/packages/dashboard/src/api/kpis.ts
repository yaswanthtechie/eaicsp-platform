
import { getAuthSession } from "./auth";

export interface KpiDashboardResponse {
  contract_version: "v1";
  generated_at: string;
  cached: boolean;
  cache_ttl_seconds?: number | null;
  filters_applied: {
    warehouse_id?: string | null;
    category?: string | null;
    start_date?: string | null;
    end_date?: string | null;
    window_days: number;
  };
  kpis: {
    fill_rate: {
      current_rate: number;
      target_rate: number;
      total_lines_ordered?: number | null;
      lines_fulfilled?: number | null;
      status: "on_target" | "warning" | "critical";
      trend: "up" | "down" | "stable";
      change_percentage?: number | null;
    };
    stockouts: {
      total_stockouts: number;
      critical_skus?: number | null;
      at_risk_skus?: number | null;
      status: "normal" | "warning" | "critical";
      trend: "improving" | "worsening" | "stable";
      by_warehouse: Array<{
        warehouse_id: string;
        stockout_count: number;
        at_risk_count?: number | null;
        total_skus?: number | null;
      }>;
    };
    open_purchase_orders: {
      total_open_orders: number;
      total_value_usd?: number | null;
      pending_approval?: number | null;
      by_status?: {
        draft?: number | null;
        approved?: number | null;
        acknowledged?: number | null;
        in_transit?: number | null;
      } | null;
    };
    on_time_delivery: {
      current_rate: number;
      target_rate: number;
      total_shipments?: number | null;
      delivered_on_time?: number | null;
      delayed?: number | null;
      status: "on_target" | "warning" | "critical";
      trend: "up" | "down" | "stable";
      change_percentage?: number | null;
    };
  };
}

export interface KpiQueryFilters {
  warehouse_id?: string | null;
  category?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  window_days?: number | null;
}

export interface AnalyticsKpi {
  title: string;
  value: number;
  format: "percent" | "number";
  status?: "on_target" | "normal" | "warning" | "critical";
}

export const MOCK_KPI_RESPONSE: KpiDashboardResponse = {
  contract_version: "v1",
  generated_at: "2026-10-15T09:00:00Z",
  cached: false,
  cache_ttl_seconds: 300,
  filters_applied: {
    warehouse_id: null,
    category: null,
    start_date: null,
    end_date: null,
    window_days: 30,
  },
  kpis: {
    fill_rate: {
      current_rate: 94.8,
      target_rate: 95,
      total_lines_ordered: 2500,
      lines_fulfilled: 2370,
      status: "warning",
      trend: "up",
      change_percentage: 1.2,
    },
    stockouts: {
      total_stockouts: 14,
      critical_skus: 5,
      at_risk_skus: 22,
      status: "warning",
      trend: "improving",
      by_warehouse: [],
    },
    open_purchase_orders: {
      total_open_orders: 42,
      total_value_usd: 125000,
      pending_approval: 8,
      by_status: {
        draft: 5,
        approved: 12,
        acknowledged: 10,
        in_transit: 15,
      },
    },
    on_time_delivery: {
      current_rate: 92.4,
      target_rate: 95,
      total_shipments: 1250,
      delivered_on_time: 1155,
      delayed: 95,
      status: "warning",
      trend: "down",
      change_percentage: -0.8,
    },
  },
};

const USE_MOCK_KPIS =
  import.meta.env.VITE_USE_MOCK_KPIS !== "false";

const KPI_API_BASE_URL =
  import.meta.env.VITE_KPI_API_BASE_URL ?? "";

const KPI_REQUEST_TIMEOUT_MS = 8000;

export class KpiApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "KpiApiError";
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonNegativeNumber(value: unknown): value is number {
  return isFiniteNumber(value) && value >= 0;
}

function isCount(value: unknown): value is number {
  return (
    isNonNegativeNumber(value) &&
    Number.isInteger(value)
  );
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isOptionalChangePercentage(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    isFiniteNumber(value)
  );
}

function isOptionalCount(value: unknown): boolean {
  return value === undefined || value === null || isCount(value);
}

function isOptionalNonNegativeNumber(value: unknown): boolean {
  return value === undefined || value === null || isNonNegativeNumber(value);
}

function isValidResponse(
  value: unknown,
): value is KpiDashboardResponse {
  if (
    !isRecord(value) ||
    value.contract_version !== "v1" ||
    typeof value.generated_at !== "string" ||
    Number.isNaN(Date.parse(value.generated_at)) ||
    typeof value.cached !== "boolean"
  ) {
    return false;
  }

  if (
    value.cache_ttl_seconds !== undefined &&
    value.cache_ttl_seconds !== null &&
    !isCount(value.cache_ttl_seconds)
  ) {
    return false;
  }

  const filters = value.filters_applied;

  if (!isRecord(filters)) {
    return false;
  }

  const windowDays = filters.window_days;

  if (!isCount(windowDays) || windowDays < 1) {
    return false;
  }

  for (const key of [
    "warehouse_id",
    "category",
    "start_date",
    "end_date",
  ] as const) {
    if (
      filters[key] !== undefined &&
      !isNullableString(filters[key])
    ) {
      return false;
    }
  }

  const kpis = value.kpis;

  if (!isRecord(kpis)) {
    return false;
  }

  const fill = kpis.fill_rate;
  const stockouts = kpis.stockouts;
  const orders = kpis.open_purchase_orders;
  const delivery = kpis.on_time_delivery;

  if (
    !isRecord(fill) ||
    !isFiniteNumber(fill.current_rate) ||
    fill.current_rate < 0 ||
    fill.current_rate > 100 ||
    !isFiniteNumber(fill.target_rate) ||
    fill.target_rate < 0 ||
    fill.target_rate > 100 ||
    !isOptionalCount(fill.total_lines_ordered) ||
    !isOptionalCount(fill.lines_fulfilled) ||
    !["on_target", "warning", "critical"].includes(
      String(fill.status),
    ) ||
    !["up", "down", "stable"].includes(
      String(fill.trend),
    ) ||
    !isOptionalChangePercentage(fill.change_percentage)
  ) {
    return false;
  }

  if (
    !isRecord(stockouts) ||
    !isCount(stockouts.total_stockouts) ||
    !isOptionalCount(stockouts.critical_skus) ||
    !isOptionalCount(stockouts.at_risk_skus) ||
    !["normal", "warning", "critical"].includes(
      String(stockouts.status),
    ) ||
    !["improving", "worsening", "stable"].includes(
      String(stockouts.trend),
    ) ||
    !Array.isArray(stockouts.by_warehouse)
  ) {
    return false;
  }

  for (const warehouse of stockouts.by_warehouse) {
    if (
      !isRecord(warehouse) ||
      typeof warehouse.warehouse_id !== "string" ||
      !/^WH-[A-Z]{3}-\d{2}$/.test(warehouse.warehouse_id) ||
      !isCount(warehouse.stockout_count) ||
      !isOptionalCount(warehouse.at_risk_count) ||
      !isOptionalCount(warehouse.total_skus)
    ) {
      return false;
    }
  }

  if (
    !isRecord(orders) ||
    !isCount(orders.total_open_orders) ||
    !isOptionalNonNegativeNumber(orders.total_value_usd) ||
    !isOptionalCount(orders.pending_approval) ||
    (orders.by_status !== undefined &&
      orders.by_status !== null &&
      (!isRecord(orders.by_status) ||
        !isOptionalCount(orders.by_status.draft) ||
        !isOptionalCount(orders.by_status.approved) ||
        !isOptionalCount(orders.by_status.acknowledged) ||
        !isOptionalCount(orders.by_status.in_transit)))
  ) {
    return false;
  }

  if (
    !isRecord(delivery) ||
    !isFiniteNumber(delivery.current_rate) ||
    delivery.current_rate < 0 ||
    delivery.current_rate > 100 ||
    !isFiniteNumber(delivery.target_rate) ||
    delivery.target_rate < 0 ||
    delivery.target_rate > 100 ||
    !isOptionalCount(delivery.total_shipments) ||
    !isOptionalCount(delivery.delivered_on_time) ||
    !isOptionalCount(delivery.delayed) ||
    !["on_target", "warning", "critical"].includes(
      String(delivery.status),
    ) ||
    !["up", "down", "stable"].includes(
      String(delivery.trend),
    ) ||
    !isOptionalChangePercentage(delivery.change_percentage)
  ) {
    return false;
  }

  return true;
}

export function mapKpiResponse(
  response: KpiDashboardResponse,
): AnalyticsKpi[] {
  return [
    {
      title: "Order Fill Rate",
      value: response.kpis.fill_rate.current_rate,
      format: "percent",
      status: response.kpis.fill_rate.status,
    },
    {
      title: "Inventory Stockouts",
      value: response.kpis.stockouts.total_stockouts,
      format: "number",
      status: response.kpis.stockouts.status,
    },
    {
      title: "Open Purchase Orders",
      value: response.kpis.open_purchase_orders.total_open_orders,
      format: "number",
    },
    {
      title: "On-Time Delivery",
      value: response.kpis.on_time_delivery.current_rate,
      format: "percent",
      status: response.kpis.on_time_delivery.status,
    },
  ];
}

export async function fetchKpiDashboard(
  filters?: KpiQueryFilters,
): Promise<KpiDashboardResponse> {
  if (USE_MOCK_KPIS) {
    return MOCK_KPI_RESPONSE;
  }

  const session = getAuthSession();

  if (!session) {
    throw new KpiApiError(
      "Sign in with a real dashboard session to load live KPIs.",
      401,
    );
  }

  const baseUrl = KPI_API_BASE_URL.replace(/\/+$/, "");
  const queryParams = new URLSearchParams();
  if (filters?.warehouse_id) {
    queryParams.set("warehouse_id", filters.warehouse_id);
  }
  if (filters?.category) {
    queryParams.set("category", filters.category);
  }
  if (filters?.start_date) {
    queryParams.set("start_date", filters.start_date);
  }
  if (filters?.end_date) {
    queryParams.set("end_date", filters.end_date);
  }
  if (filters?.window_days !== undefined && filters.window_days !== null && filters.window_days >= 1) {
    queryParams.set("window_days", String(filters.window_days));
  }

  const queryString = queryParams.toString();
  const requestUrl = `${baseUrl}/api/v1/analytics/kpis${queryString ? `?${queryString}` : ""}`;
  let response: Response;

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    KPI_REQUEST_TIMEOUT_MS,
  );
  try {
    response = await fetch(
      requestUrl,
      {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          Accept: "application/json",
        },
        signal: controller.signal,
      },
    );
  } catch (error: unknown) {
    const timedOut =
      error instanceof DOMException &&
      error.name === "AbortError";
    
    throw new KpiApiError(
      timedOut
        ? "The KPI service took too long to respond."
        : "The KPI service is unavailable. Check the connection and retry.",
    );
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new KpiApiError(
      response.status >= 500
        ? "The KPI service is temporarily unavailable."
        : `Unable to load KPIs (HTTP ${response.status}).`,
      response.status,
    );
  }

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new KpiApiError(
      "The KPI service returned invalid JSON.",
    );
  }

  if (!isValidResponse(payload)) {
    throw new KpiApiError(
      "The KPI service response does not match the expected contract.",
    );
  }

  return payload;
}
