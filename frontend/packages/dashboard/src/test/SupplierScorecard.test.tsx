import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchSupplierScorecard,
  type SupplierScorecardRow,
} from "../api/supplierScorecard";
import SupplierScorecard from "../pages/SupplierScorecard";
vi.mock("../api/supplierScorecard", () => ({
  fetchSupplierScorecard: vi.fn(),
}));

const mockSuppliers: SupplierScorecardRow[] = [
  {
    supplier_id: "SUP-00007",
    supplier_name: "ALPHA SANCTIONS CORP",
    on_time_delivery_percent: null,
    risk: {
      supplier_id: "SUP-00007",
      score: 85,
      tier: "Critical",
      top_reasons: [],
      client_risk_features: null,
    },
    risk_error: null,
  },
  {
    supplier_id: "SUP-00023",
    supplier_name: "TEST EU ENTITY 01",
    on_time_delivery_percent: null,
    risk: {
      supplier_id: "SUP-00023",
      score: 65,
      tier: "Critical",
      top_reasons: [
        "Designated on EU-CONSOLIDATED (critical compliance risk)",
      ],
      client_risk_features: null,
    },
    risk_error: null,
  },
  {
    supplier_id: "SUP-00045",
    supplier_name: "TEST UN ENTITY 01",
    on_time_delivery_percent: null,
    risk: {
      supplier_id: "SUP-00045",
      score: 95,
      tier: "Critical",
      top_reasons: [],
      client_risk_features: null,
    },
    risk_error: null,
  },
];

describe("C8 Supplier Risk Scorecard", () => {
  beforeEach(() => {
    vi.mocked(fetchSupplierScorecard).mockResolvedValue(mockSuppliers);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("displays the three actual suppliers with their IDs", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ALPHA SANCTIONS CORP")).toBeInTheDocument();
    expect(screen.getByText("SUP-00007")).toBeInTheDocument();

    expect(screen.getByText("TEST EU ENTITY 01")).toBeInTheDocument();
    expect(screen.getByText("SUP-00023")).toBeInTheDocument();

    expect(screen.getByText("TEST UN ENTITY 01")).toBeInTheDocument();
    expect(screen.getByText("SUP-00045")).toBeInTheDocument();
  });

  it("displays the actual risk score and tier for all three suppliers", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    await screen.findByText("ALPHA SANCTIONS CORP");

    expect(screen.getByText("85.0")).toBeInTheDocument();
    expect(screen.getByText("65.0")).toBeInTheDocument();
    expect(screen.getByText("95.0")).toBeInTheDocument();
    expect(screen.getAllByText("Critical")).toHaveLength(3);
  });

  it("displays Not tracked for missing On-time-delivery data", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    await screen.findByText("ALPHA SANCTIONS CORP");

    expect(screen.getAllByText("Not tracked")).toHaveLength(3);
  });

  it("displays Unavailable for missing incident data", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    await screen.findByText("ALPHA SANCTIONS CORP");

    expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  });

  it("filters suppliers by supplier ID", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    await screen.findByText("ALPHA SANCTIONS CORP");

    const searchInput = screen.getByRole("searchbox");

    fireEvent.change(searchInput, {
      target: { value: "SUP-00023" },
    });

    expect(screen.getByText("TEST EU ENTITY 01")).toBeInTheDocument();
    expect(screen.queryByText("ALPHA SANCTIONS CORP")).not.toBeInTheDocument();
    expect(screen.queryByText("TEST UN ENTITY 01")).not.toBeInTheDocument();
  });

  it("shows the actual risk reason when TEST EU ENTITY 01 is expanded", async () => {
    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    await screen.findByText("TEST EU ENTITY 01");

    const supplierName = screen.getByText("TEST EU ENTITY 01");
    const supplierRow = supplierName.closest("tr");

    expect(supplierRow).not.toBeNull();

    fireEvent.click(supplierRow!);

    expect(
      await screen.findByText(
        "Designated on EU-CONSOLIDATED (critical compliance risk)",
      ),
    ).toBeInTheDocument();
  });

  it("keeps supplier visible when risk data is unavailable", async () => {
    vi.mocked(fetchSupplierScorecard).mockResolvedValue([
      {
        supplier_id: "SUP-00007",
        supplier_name: "ALPHA SANCTIONS CORP",
        on_time_delivery_percent: null,
        risk: null,
        risk_error: "Risk service unavailable",
      },
    ]);

    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ALPHA SANCTIONS CORP")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });

  it("displays loading state while API request is pending", () => {
    vi.mocked(fetchSupplierScorecard).mockReturnValue(
      new Promise(() => {}),
    );

    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays error state when API request fails", async () => {
    vi.mocked(fetchSupplierScorecard).mockRejectedValue(
      new Error("API request failed"),
    );

    render(
      <MemoryRouter>
        <SupplierScorecard />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/failed|unable|could not/i),
    ).toBeInTheDocument();
  });

  function row(
    supplierId: string,
    name: string,
    score: number | null,
    tier: "Low" | "Medium" | "High" | "Critical" | null,
    onTime: number | null,
    riskError: string | null = null,
  ): SupplierScorecardRow {
    return {
      supplier_id: supplierId,
      supplier_name: name,
      on_time_delivery_percent: onTime,
      risk:
        riskError === null
          ? {
              supplier_id: supplierId,
              score,
              tier,
              top_reasons: [],
              client_risk_features: null,
            }
          : null,
      risk_error: riskError,
    };
  }

  const sortSuppliers: SupplierScorecardRow[] = [
    row("SUP-00022", "Bluepeak Enterprises Inc", 48, "Medium", 88),
    row("SUP-00021", "Evergreen Supplies GmbH", null, null, null),
    row("SUP-00007", "ALPHA SANCTIONS CORP", 85, "Critical", 96),
    ];

  function supplierOrder(): string[] {
    return Array.from(
      document.querySelectorAll('tr[aria-label^="Show risk reasons for "]'),
    ).map((tr) =>
      (tr.getAttribute("aria-label") ?? "").replace("Show risk reasons for ", ""),
    );
  }

  describe("C8 Supplier Risk Scorecard sorting and partial failure", () => {
    afterEach(() => {
      cleanup();
      vi.clearAllMocks();
    });

    async function renderScorecard(data: SupplierScorecardRow[]) {
      vi.mocked(fetchSupplierScorecard).mockResolvedValue(data);
      render(
        <MemoryRouter>
          <SupplierScorecard />
        </MemoryRouter>,
      );
      await screen.findByText("ALPHA SANCTIONS CORP");
    }

    it("shows the highest risk first by default, missing scores last", async () => {
      await renderScorecard(sortSuppliers);

      expect(supplierOrder()).toEqual([
        "ALPHA SANCTIONS CORP",
        "Bluepeak Enterprises Inc",
        "Evergreen Supplies GmbH",
      ]);
    });

    it("flips the risk score order on click, keeping missing scores last", async () => {
      await renderScorecard(sortSuppliers);

      fireEvent.click(screen.getByRole("button", { name: /^Risk score/ }));

      expect(supplierOrder()).toEqual([
        "Bluepeak Enterprises Inc",
        "ALPHA SANCTIONS CORP",
        "Evergreen Supplies GmbH",
      ]);
    });

    it("sorts by on-time delivery with Not tracked last", async () => {
      await renderScorecard(sortSuppliers);

      fireEvent.click(screen.getByRole("button", { name: /^On-time delivery/ }));

      expect(supplierOrder()).toEqual([
        "Bluepeak Enterprises Inc",
        "ALPHA SANCTIONS CORP",
          "Evergreen Supplies GmbH",
      ]);
    });

    it("says how many suppliers have no risk data when the risk endpoint fails", async () => {
      await renderScorecard([
        row("SUP-00007", "ALPHA SANCTIONS CORP", null, null, 96, "Request failed (503)."),
        row("SUP-00022", "Bluepeak Enterprises Inc", 48, "Medium", 88),
      ]);

      expect(screen.getByRole("status")).toHaveTextContent(
        "Risk data could not be loaded for 1 of 2 suppliers.",
      );
      expect(screen.getByText("96.0%")).toBeInTheDocument();
    });
  });
});
