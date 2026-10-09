import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NetworkStatus } from "@apollo/client";

import Dashboard from "./Dashboard";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<
    typeof import("react-router-dom")
  >("react-router-dom");

  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../hooks/usePurchaseOrders", () => ({
  usePurchaseOrders: vi.fn(),
}));

const mockedUsePurchaseOrders = vi.mocked(usePurchaseOrders);

const mockOrders = [
  {
    poNumber: "PO1001",
    supplierId: "SUP001",
    status: "DRAFT",
    totalAmount: 25000,
    expectedDelivery: "2026-08-01",
    items: [],
  },
  {
    poNumber: "PO1002",
    supplierId: "SUP001",
    status: "SENT",
    totalAmount: 18000,
    expectedDelivery: "2026-08-05",
    items: [],
  },
  {
    poNumber: "PO1003",
    supplierId: "SUP002",
    status: "SENT",
    totalAmount: 9500,
    expectedDelivery: "2026-08-08",
    items: [],
  },
  {
    poNumber: "PO1004",
    supplierId: "SUP003",
    status: "ACKNOWLEDGED",
    totalAmount: 21000,
    expectedDelivery: "2026-08-10",
    items: [],
  },
];

const renderDashboard = () => {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
};

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockedUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: mockOrders.map((order) => ({
            cursor: `cursor-${order.poNumber}`,
            node: order,
          })),
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      networkStatus: NetworkStatus.ready,
    } as ReturnType<typeof usePurchaseOrders>);
  });

  it("renders the purchase order summary", () => {
    renderDashboard();

    expect(
      screen.getByRole("heading", {
        name: "Supplier Dashboard",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText("Total POs")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Pending Acknowledgement")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Acknowledged", {
        selector: ".dashboard-card-label",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText("Total PO Value")
    ).toBeInTheDocument();

    expect(screen.getByText("4")).toBeInTheDocument();

    expect(
      screen.getByText("₹73,500.00")
    ).toBeInTheDocument();
  });

  it("shows pending acknowledgement action", () => {
    renderDashboard();

    expect(
      screen.getByText("2 POs waiting for acknowledgement")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Review POs",
      })
    ).toBeInTheDocument();
  });

  it("shows invoice action for acknowledged purchase orders", () => {
    renderDashboard();

    expect(
      screen.getByText(
        "1 acknowledged PO ready for invoicing"
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Create Invoice",
      })
    ).toBeInTheDocument();
  });

  it("navigates to purchase orders when a quick action is clicked", () => {
    renderDashboard();

    fireEvent.click(
      screen.getByRole("button", {
        name: "View Purchase Orders",
      })
    );

    expect(mockNavigate).toHaveBeenCalledWith(
      "/orders"
    );
  });

  it("shows loading state during the initial request", () => {
    mockedUsePurchaseOrders.mockReturnValue({
      data: undefined,
      loading: true,
      error: undefined,
      networkStatus: NetworkStatus.loading,
    } as ReturnType<typeof usePurchaseOrders>);

    renderDashboard();

    expect(
      screen.getByText(/loading/i)
    ).toBeInTheDocument();
  });

  it("shows error state when the request fails", () => {
    mockedUsePurchaseOrders.mockReturnValue({
      data: undefined,
      loading: false,
      error: new Error(
        "Failed to load purchase orders"
      ),
      networkStatus: NetworkStatus.error,
    } as ReturnType<typeof usePurchaseOrders>);

    renderDashboard();

    expect(
      screen.getByText("Something went wrong.")
    ).toBeInTheDocument();
  });

  it("navigates to shipments from quick actions", () => {
    renderDashboard();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Track Shipments",
      })
    );

    expect(mockNavigate).toHaveBeenCalledWith(
      "/shipments"
    );
  });
});