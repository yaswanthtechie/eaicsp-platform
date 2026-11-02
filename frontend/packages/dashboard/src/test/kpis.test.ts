import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  getAuthSession: vi.fn(),
}));

vi.mock("../api/auth", () => ({
  getAuthSession: authMocks.getAuthSession,
}));

function makeResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

async function loadApi(useMock = "false", baseUrl = "") {
  vi.resetModules();
  vi.stubEnv("VITE_USE_MOCK_KPIS", useMock);
  vi.stubEnv("VITE_KPI_API_BASE_URL", baseUrl);

  return import("../api/kpis");
}

describe("KPI API", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    authMocks.getAuthSession.mockReset();

    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("maps the order fill rate correctly", async () => {
    const api = await loadApi("true");
    const result = api.mapKpiResponse(api.MOCK_KPI_RESPONSE);

    expect(result[0]).toEqual({
      title: "Order Fill Rate",
      value: 94.8,
      format: "percent",
      status: "warning",
    });
  });

  it("maps inventory stockouts correctly", async () => {
    const api = await loadApi("true");
    const result = api.mapKpiResponse(api.MOCK_KPI_RESPONSE);

    expect(result[1]).toEqual({
      title: "Inventory Stockouts",
      value: 14,
      format: "number",
      status: "warning",
    });
  });

  it("maps open purchase orders correctly", async () => {
    const api = await loadApi("true");
    const result = api.mapKpiResponse(api.MOCK_KPI_RESPONSE);

    expect(result[2]).toEqual({
      title: "Open Purchase Orders",
      value: 42,
      format: "number",
    });
  });

  it("maps on-time delivery correctly", async () => {
    const api = await loadApi("true");
    const result = api.mapKpiResponse(api.MOCK_KPI_RESPONSE);

    expect(result[3]).toEqual({
      title: "On-Time Delivery",
      value: 92.4,
      format: "percent",
      status: "warning",
    });
  });

  it("returns four KPI cards", async () => {
    const api = await loadApi("true");

    expect(api.mapKpiResponse(api.MOCK_KPI_RESPONSE)).toHaveLength(4);
  });

  it("returns mock data without making an API request", async () => {
    const api = await loadApi("true");

    await expect(api.fetchKpiDashboard()).resolves.toEqual(
      api.MOCK_KPI_RESPONSE,
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects when no user session exists", async () => {
    authMocks.getAuthSession.mockReturnValue(null);

    const api = await loadApi("false");

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 401,
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the access token with the API request", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse(api.MOCK_KPI_RESPONSE));

    await api.fetchKpiDashboard();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/analytics/kpis",
      {
        headers: {
          Authorization: "Bearer test-access-token",
          Accept: "application/json",
        },
        signal: expect.any(AbortSignal),
      },
    );
  });

  it("times out when the KPI service does not respond", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");

    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

    vi.useFakeTimers();

    const request = api.fetchKpiDashboard();
    const assertion = expect(request).rejects.toThrow(
      "The KPI service took too long to respond.",
    );

    await vi.advanceTimersByTimeAsync(8000);
    await assertion;

    vi.useRealTimers();
  });

  it("uses the configured API base URL", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false", "http://127.0.0.1:8000");
    fetchMock.mockResolvedValue(makeResponse(api.MOCK_KPI_RESPONSE));

    await api.fetchKpiDashboard();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analytics/kpis",
      expect.any(Object),
    );
  });

  it("handles HTTP 400 errors", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}, 400));

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 400,
    });
  });

  it("handles HTTP 401 errors", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}, 401));

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 401,
    });
  });

  it("handles HTTP 403 errors", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}, 403));

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 403,
    });
  });

  it("handles server errors", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}, 500));

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 500,
      message: "The KPI service is temporarily unavailable.",
    });
  });

  it("handles network failures", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockRejectedValue(new Error("Network unavailable"));

    await expect(api.fetchKpiDashboard()).rejects.toThrow(
      "The KPI service is unavailable. Check the connection and retry.",
    );
  });

  it("handles invalid JSON responses", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new Error("Invalid JSON")),
    });

    await expect(api.fetchKpiDashboard()).rejects.toThrow(
      "The KPI service returned invalid JSON.",
    );
  });

  it("rejects unsupported contract versions", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");

    fetchMock.mockResolvedValue(
      makeResponse({
        ...api.MOCK_KPI_RESPONSE,
        contract_version: "v2",
      }),
    );

    await expect(api.fetchKpiDashboard()).rejects.toThrow(
      "The KPI service response does not match the expected contract.",
    );
  });

  it("rejects responses missing required KPI fields", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}));

    await expect(api.fetchKpiDashboard()).rejects.toThrow(
      "The KPI service response does not match the expected contract.",
    );
  });

  it("handles HTTP 503 service errors", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse({}, 503));

    await expect(api.fetchKpiDashboard()).rejects.toMatchObject({
      status: 503,
      message: "The KPI service is temporarily unavailable.",
    });
  });

  it("appends filter query parameters when provided", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    fetchMock.mockResolvedValue(makeResponse(api.MOCK_KPI_RESPONSE));

    await api.fetchKpiDashboard({
      warehouse_id: "WH-ORD-01",
      category: "industrial",
      start_date: "2026-10-01",
      end_date: "2026-10-15",
      window_days: 14,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/analytics/kpis?warehouse_id=WH-ORD-01&category=industrial&start_date=2026-10-01&end_date=2026-10-15&window_days=14",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-access-token",
        }),
      }),
    );
  });

  it("accepts valid responses with null secondary metrics and nullable rates", async () => {
    authMocks.getAuthSession.mockReturnValue({
      access_token: "test-access-token",
    });

    const api = await loadApi("false");
    const responseWithNulls = {
      ...api.MOCK_KPI_RESPONSE,
      kpis: {
        ...api.MOCK_KPI_RESPONSE.kpis,
        fill_rate: {
          ...api.MOCK_KPI_RESPONSE.kpis.fill_rate,
          current_rate: null,
          status: "no_data",
        },
        stockouts: {
          ...api.MOCK_KPI_RESPONSE.kpis.stockouts,
          critical_skus: null,
          at_risk_skus: null,
          by_warehouse: [
            {
              warehouse_id: "WH-BLR-01",
              stockout_count: 5,
              at_risk_count: null,
              total_skus: 100,
            },
          ],
        },
        open_purchase_orders: {
          ...api.MOCK_KPI_RESPONSE.kpis.open_purchase_orders,
          total_value_usd: null,
          pending_approval: null,
          by_status: {
            draft: null,
            approved: 12,
            acknowledged: 10,
            in_transit: 15,
          },
        },
        on_time_delivery: {
          ...api.MOCK_KPI_RESPONSE.kpis.on_time_delivery,
          current_rate: null,
          status: "no_data",
        },
      },
    };

    fetchMock.mockResolvedValue(makeResponse(responseWithNulls));

    const result = await api.fetchKpiDashboard();
    expect(result.kpis.fill_rate.current_rate).toBeNull();
    expect(result.kpis.fill_rate.status).toBe("no_data");
    expect(result.kpis.stockouts.critical_skus).toBeNull();
    expect(result.kpis.open_purchase_orders.total_value_usd).toBeNull();
    expect(result.kpis.open_purchase_orders.by_status.draft).toBeNull();
    expect(result.kpis.on_time_delivery.current_rate).toBeNull();
    expect(result.kpis.on_time_delivery.status).toBe("no_data");
  });

  it("maps nullable current_rate and no_data status correctly", async () => {
    const api = await loadApi("true");
    const responseWithNullRates = {
      ...api.MOCK_KPI_RESPONSE,
      kpis: {
        ...api.MOCK_KPI_RESPONSE.kpis,
        fill_rate: {
          ...api.MOCK_KPI_RESPONSE.kpis.fill_rate,
          current_rate: null,
          status: "no_data" as const,
        },
        on_time_delivery: {
          ...api.MOCK_KPI_RESPONSE.kpis.on_time_delivery,
          current_rate: null,
          status: "no_data" as const,
        },
      },
    };

    const result = api.mapKpiResponse(responseWithNullRates);
    expect(result[0]).toEqual({
      title: "Order Fill Rate",
      value: null,
      format: "percent",
      status: "no_data",
    });
    expect(result[3]).toEqual({
      title: "On-Time Delivery",
      value: null,
      format: "percent",
      status: "no_data",
    });
  });
});
