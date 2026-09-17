import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Shipments from "./Shipments";
import { getShipments } from "../api/shipments";
import { getSupplierId } from "../auth/tokenStorage";

vi.mock("../api/shipments", () => ({
  getShipments: vi.fn(),
}));

vi.mock("../auth/tokenStorage", () => ({
  getSupplierId: vi.fn(),
}));

const mockedGetShipments = vi.mocked(getShipments);
const mockedGetSupplierId = vi.mocked(getSupplierId);

const mockShipments = [
  {
    id: "SHP-1001",
    poNumber: "PO1001",
    supplierId: "SUP001",
    product: "Laptop",
    expectedDelivery: "2026-08-01",
    status: "PROCESSING" as const,
    progress: 25,
  },
  {
    id: "SHP-1002",
    poNumber: "PO1002",
    supplierId: "SUP001",
    product: "Monitor",
    expectedDelivery: "2026-08-05",
    status: "IN_TRANSIT" as const,
    progress: 65,
  },
  {
    id: "SHP-1003",
    poNumber: "PO1003",
    supplierId: "SUP002",
    product: "Keyboard",
    expectedDelivery: "2026-08-08",
    status: "OUT_FOR_DELIVERY" as const,
    progress: 90,
  },
  {
    id: "SHP-1004",
    poNumber: "PO1004",
    supplierId: "SUP003",
    product: "Server Equipment",
    expectedDelivery: "2026-08-10",
    status: "DELIVERED" as const,
    progress: 100,
  },
];

const renderShipments = () => {
  return render(
    <MemoryRouter>
      <Shipments />
    </MemoryRouter>,
  );
};

describe("Shipments", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedGetSupplierId.mockReturnValue("SUP001");

    mockedGetShipments.mockResolvedValue(
      mockShipments,
    );
  });

  it("renders the shipment tracking page", async () => {
    renderShipments();

    expect(
      screen.getByRole("heading", {
        name: "Shipment Tracking",
        level: 1,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Track purchase order deliveries and shipment progress.",
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByText("PO1001"),
    ).toBeInTheDocument();
  });

  it("loads shipments from the API", async () => {
    renderShipments();

    expect(
      await screen.findByText("PO1001"),
    ).toBeInTheDocument();

    expect(
      mockedGetShipments,
    ).toHaveBeenCalledTimes(1);
  });

  it("shows only shipments for the current supplier", async () => {
    renderShipments();

    expect(
      await screen.findByText("PO1001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("PO1002"),
    ).toBeInTheDocument();

    expect(
      screen.queryByText("PO1003"),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("PO1004"),
    ).not.toBeInTheDocument();
  });

  it("shows shipment summary counts", async () => {
    renderShipments();

    expect(
      await screen.findByText("PO1001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Total Shipments"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("In Transit"),
    ).toHaveLength(2);

    expect(
      screen.getByText("Delivered"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("2"),
    ).toBeInTheDocument();
  });

  it("shows shipment status", async () => {
    renderShipments();

    expect(
      await screen.findByText("Processing"),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("In Transit"),
    ).toHaveLength(2);
  });

  it("shows shipment details", async () => {
    renderShipments();

    expect(
      await screen.findByText("PO1001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("SHP-1001"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Laptop"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("2026-08-01"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Monitor"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("2026-08-05"),
    ).toBeInTheDocument();
  });

  it("shows delivery progress", async () => {
    renderShipments();

    expect(
      await screen.findByRole("progressbar", {
        name: "PO1001 delivery progress",
      }),
    ).toHaveAttribute(
      "aria-valuenow",
      "25",
    );

    expect(
      screen.getByRole("progressbar", {
        name: "PO1002 delivery progress",
      }),
    ).toHaveAttribute(
      "aria-valuenow",
      "65",
    );

    expect(
      screen.getByText("25%"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("65%"),
    ).toBeInTheDocument();
  });

  it("shows loading state while shipments are loading", () => {
    mockedGetShipments.mockReturnValue(
      new Promise(() => {}),
    );

    renderShipments();

    expect(
      screen.getByRole("status", {
        name: "Loading shipments...",
      }),
    ).toBeInTheDocument();
  });

  it("shows error state when shipment loading fails", async () => {
    mockedGetShipments.mockRejectedValue(
      new Error("Failed to load shipments"),
    );

    renderShipments();

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "Unable to load shipments. Please try again.",
    );
  });

  it("shows empty state when the supplier has no shipments", async () => {
    mockedGetShipments.mockResolvedValue(
      mockShipments.filter(
        (shipment) =>
          shipment.supplierId !== "SUP001",
      ),
    );

    renderShipments();

    expect(
      await screen.findByText(
        "No shipments available",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "There are currently no shipments to track.",
      ),
    ).toBeInTheDocument();
  });

  it("shows both summary and shipment status when the same status appears", async () => {
    renderShipments();

    await screen.findByText("PO1002");

    expect(
      screen.getAllByText("In Transit"),
    ).toHaveLength(2);
  });
});