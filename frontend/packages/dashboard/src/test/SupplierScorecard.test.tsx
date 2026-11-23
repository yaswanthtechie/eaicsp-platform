import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SupplierScorecard from "../pages/SupplierScorecard";
import { fetchSupplierScorecard } from "../api/supplierScoreCard";

vi.mock("../api/supplierScoreCard", () => ({
  fetchSupplierScorecard: vi.fn(),
}));

const mockSuppliers = [
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
      score: 85,
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
      score: 85,
      tier: "Critical",
      top_reasons: [],
      client_risk_features: null,
    },
    risk_error: null,
  },
];

describe("C8 Supplier Risk Scorecard", () => {
  beforeEach(() => {
    vi.mocked(fetchSupplierScorecard).mockResolvedValue(mockSuppliers as Awaited<ReturnType<typeof fetchSupplierScorecard>>);
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

    expect(screen.getAllByText("85.0")).toHaveLength(3);
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
});
