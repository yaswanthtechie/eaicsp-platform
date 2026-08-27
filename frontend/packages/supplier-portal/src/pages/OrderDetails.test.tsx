import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OrderDetails from "./OrderDetails";

vi.mock("../hooks/useOrderDetails", () => ({
  useOrderDetails: vi.fn(),
}));

vi.mock("../hooks/useAcknowledgePO", () => ({
  useAcknowledgePO: vi.fn(),
}));

vi.mock("../components/StatusBadge", () => ({
  default: ({ status }: { status: string }) => (
    <div data-testid="status-badge">{status}</div>
  ),
}));

vi.mock("../components/Loading", () => ({
  default: () => <div data-testid="loading">Loading</div>,
}));

vi.mock("../components/ErrorState", () => ({
  default: () => <div data-testid="error-state">Error</div>,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { useOrderDetails } from "../hooks/useOrderDetails";
import { useAcknowledgePO } from "../hooks/useAcknowledgePO";

const mockUseOrderDetails = vi.mocked(useOrderDetails);
const mockUseAcknowledgePO = vi.mocked(useAcknowledgePO);

describe("OrderDetails", () => {
  beforeEach(() => {
    vi.clearAllMocks();

mockUseAcknowledgePO.mockReturnValue({
  acknowledgePO: vi.fn(),
  loading: false,
  called: false,
  client: {} as never,
  reset: vi.fn(),
  acknowledgePurchaseOrder: vi.fn(),
} as never);

    mockUseOrderDetails.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [
            {
              cursor: "cursor-1",
              node: {
                po_number: "PO-1001",
                supplier_id: "SUP-1",
                status: "sent",
                total_amount: 1500,
                expected_delivery: "2026-08-30",
                items: [
                  {
                    sku: "SKU-001",
                    product_name: "Laptop",
                    quantity: 2,
                    unit_price: 500,
                  },
                  {
                    sku: "SKU-002",
                    product_name: "Mouse",
                    quantity: 1,
                    unit_price: 500,
                  },
                ],
              },
            },
          ],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
    } as never);
  });

  it("renders purchase order details", () => {
    render(
      <MemoryRouter initialEntries={["/orders/PO-1001"]}>
        <Routes>
          <Route
            path="/orders/:poNumber"
            element={<OrderDetails />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", {
        name: "Purchase Order Details",
      })
    ).toBeInTheDocument();

    expect(screen.getByText("PO-1001")).toBeInTheDocument();
    expect(screen.getByText("SUP-1")).toBeInTheDocument();

    expect(
      screen.getByText("30/8/2026")
    ).toBeInTheDocument();

    expect(
      screen.getByTestId("status-badge")
    ).toHaveTextContent("sent");

    expect(screen.getByText("Laptop")).toBeInTheDocument();
    expect(screen.getByText("Mouse")).toBeInTheDocument();

    expect(screen.getByText("SKU-001")).toBeInTheDocument();
    expect(screen.getByText("SKU-002")).toBeInTheDocument();

    expect(screen.getAllByText("Quantity:")).toHaveLength(2);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: /Total:/,
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Acknowledge",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Back to Orders",
      })
    ).toBeInTheDocument();
  });
});