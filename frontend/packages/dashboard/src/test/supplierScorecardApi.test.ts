import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchSupplierScorecard } from "../api/supplierScorecard";

vi.mock("../api/auth", () => ({
  getAuthSession: () => ({ access_token: "test-token" }),
  refreshAuthSession: vi.fn(),
}));

const PERFORMANCE_URL = "/api/v1/inventory/suppliers/performance";

const performance = [
  {
    supplier_id: "SUP-00007",
    supplier_name: "ALPHA SANCTIONS CORP",
    received_po_count: 0,
    on_time_po_count: 0,
    on_time_delivery_percent: null,
    total_po_count: 0,
    open_po_count: 0,
    late_po_count: 0,
  },
  {
    supplier_id: "SUP-00019",
    supplier_name: "Unity Manufacturing GmbH",
    received_po_count: 10,
    on_time_po_count: 9,
    on_time_delivery_percent: 90,
    total_po_count: 10,
    open_po_count: 0,
    late_po_count: 1,
  },
];

const risk = {
  supplier_id: "SUP-00007",
  score: 85,
  tier: "Critical",
  top_factors: [],
  top_evidence_articles: [],
  computed_at: "2026-11-20T10:30:00Z",
  top_reasons: ["Designated on OFAC-SDN (critical compliance risk)"],
  client_risk_features: null,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubGateway(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const handler = routes[String(input)];
    return Promise.resolve(handler ? handler() : json({}, 404));
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("fetchSupplierScorecard", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_USE_MOCK_SUPPLIER_SCORECARD", "false");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("keeps every supplier when one risk call fails", async () => {
    stubGateway({
      [PERFORMANCE_URL]: () => json(performance),
      "/api/v1/suppliers/SUP-00007/risk-score": () => json(risk),
      "/api/v1/suppliers/SUP-00019/risk-score": () =>
        json({ error_code: "RISK_UNAVAILABLE" }, 503),
    });

    const rows = await fetchSupplierScorecard();

    expect(rows.map((row) => row.supplier_id)).toEqual([
      "SUP-00007",
      "SUP-00019",
    ]);
    expect(rows[0].risk?.score).toBe(85);
    expect(rows[0].risk_error).toBeNull();
    expect(rows[1].risk).toBeNull();
    expect(rows[1].risk_error).toBe("Request failed (503).");
    expect(rows[1].on_time_delivery_percent).toBe(90);
  });

  it("keeps a missing on-time value as null, not 0", async () => {
    stubGateway({
      [PERFORMANCE_URL]: () => json(performance),
      "/api/v1/suppliers/SUP-00007/risk-score": () => json(risk),
      "/api/v1/suppliers/SUP-00019/risk-score": () =>
        json({ ...risk, supplier_id: "SUP-00019" }),
    });

    const rows = await fetchSupplierScorecard();

    expect(rows[0].on_time_delivery_percent).toBeNull();
  });

  it("says what is missing when the performance endpoint is down", async () => {
    const fetchMock = stubGateway({
      [PERFORMANCE_URL]: () => json({ detail: "unavailable" }, 503),
    });

    await expect(fetchSupplierScorecard()).rejects.toThrow(
      /Supplier list and on-time data are unavailable \(Request failed \(503\)\.\)/,
    );
    // No risk calls without a supplier list.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});