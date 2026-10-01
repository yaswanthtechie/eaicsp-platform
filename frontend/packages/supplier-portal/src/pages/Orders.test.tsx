import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";

import Orders from "./Orders";
import { logout } from "../auth/logout";

vi.mock("../hooks/usePurchaseOrders", () => ({
  usePurchaseOrders: vi.fn(),
}));

vi.mock("../auth/logout", () => ({
  logout: vi.fn(),
}));

vi.mock("../components/POCard", () => ({
  default: ({ order }: { order: { poNumber: string } }) => (
    <div data-testid="po-card">{order.poNumber}</div>
  ),
}));

vi.mock("../components/EmptyState", () => ({
  default: () => <div data-testid="empty-state">No orders</div>,
}));

vi.mock("../components/ErrorState", () => ({
  default: () => <div data-testid="error-state">Error</div>,
}));

vi.mock("../components/Loading", () => ({
  default: () => <div data-testid="loading">Loading</div>,
}));

/*
 * jsdom does not provide real layout or scroll measurements.
 * Therefore, this mock returns all items so the Orders component
 * can be tested deterministically. Actual viewport windowing
 * behavior is provided by @tanstack/react-virtual in the browser.
 */
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 150,
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        start: index * 150,
        size: 150,
        key: index,
      })),
  }),
}));

import { usePurchaseOrders } from "../hooks/usePurchaseOrders";

const LocationDisplay = () => {
  const location = useLocation();

  return <div data-testid="location">{location.pathname}</div>;
};

const mockUsePurchaseOrders = vi.mocked(usePurchaseOrders);

describe("Orders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders purchase orders", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [
            {
              cursor: "cursor-1",
              node: {
                poNumber: "PO-1001",
                supplierId: "SUP-1",
                status: "SENT",
                totalAmount: 1000,
                expectedDelivery: "2026-08-30",
                items: [],
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
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    expect(screen.getByText("Purchase Orders")).toBeInTheDocument();
    expect(screen.getByTestId("po-card")).toHaveTextContent("PO-1001");
  });

  it("shows empty state when there are no purchase orders", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: undefined,
      loading: true,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 1,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("shows error state when loading fails without data", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: undefined,
      loading: false,
      error: new Error("Failed to load orders"),
      fetchMore: vi.fn(),
      networkStatus: 8,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    expect(screen.getByTestId("error-state")).toBeInTheDocument();
  });

  it("loads the next page using the end cursor", async () => {
    const fetchMore = vi.fn().mockResolvedValue({});

    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [
            {
              cursor: "cursor-1",
              node: {
                poNumber: "PO-1001",
                supplierId: "SUP-1",
                status: "SENT",
                totalAmount: 1000,
                expectedDelivery: "2026-08-30",
                items: [],
              },
            },
          ],
          pageInfo: {
            hasNextPage: true,
            endCursor: "cursor-1",
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore,
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    const loadMoreButton = screen.getByRole("button", {
      name: "Load More",
    });

    loadMoreButton.click();

    expect(fetchMore).toHaveBeenCalledWith({
      variables: {
        first: 20,
        after: "cursor-1",
        status: undefined,
        poNumber: undefined,
        minAmount: undefined,
        maxAmount: undefined,
        startDate: undefined,
        endDate: undefined,
      },
    });
  });

  it("passes search and filter values to usePurchaseOrders", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    const poInput = screen.getByPlaceholderText("Search PO Number");
    const minAmountInput = screen.getByPlaceholderText("Min Amount");
    const maxAmountInput = screen.getByPlaceholderText("Max Amount");

    fireEvent.change(poInput, {
      target: { value: "PO-1005" },
    });

    fireEvent.change(minAmountInput, {
      target: { value: "1000" },
    });

    fireEvent.change(maxAmountInput, {
      target: { value: "5000" },
    });

    expect(mockUsePurchaseOrders).toHaveBeenLastCalledWith({
      first: 20,
      after: null,
      status: undefined,
      poNumber: "PO-1005",
      minAmount: 1000,
      maxAmount: 5000,
      startDate: undefined,
      endDate: undefined,
    });
  });

  it("filters purchase orders by status", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Acknowledged",
      })
    );

    expect(mockUsePurchaseOrders).toHaveBeenLastCalledWith({
      first: 20,
      after: null,
      status: "ACKNOWLEDGED",
      poNumber: undefined,
      minAmount: undefined,
      maxAmount: undefined,
      startDate: undefined,
      endDate: undefined,
    });
  });

  it("passes date filter values to usePurchaseOrders", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Start Date"), {
      target: { value: "2026-08-01" },
    });

    fireEvent.change(screen.getByLabelText("End Date"), {
      target: { value: "2026-08-31" },
    });

    expect(mockUsePurchaseOrders).toHaveBeenLastCalledWith({
      first: 20,
      after: null,
      status: undefined,
      poNumber: undefined,
      minAmount: undefined,
      maxAmount: undefined,
      startDate: "2026-08-01",
      endDate: "2026-08-31",
    });
  });

  it("navigates to the new invoice page", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter initialEntries={["/orders"]}>
        <Orders />
        <LocationDisplay />
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole("button", { name: "New Invoice" })
    );

    expect(screen.getByTestId("location")).toHaveTextContent(
      "/invoices/new"
    );
  });

  it("calls logout when the Logout button is clicked", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [],
          pageInfo: {
            hasNextPage: false,
            endCursor: null,
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 7,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Logout" })
    );

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("disables Load More while loading the next page", () => {
    mockUsePurchaseOrders.mockReturnValue({
      data: {
        purchaseOrders: {
          edges: [
            {
              cursor: "cursor-1",
              node: {
                poNumber: "PO-1001",
                supplierId: "SUP-1",
                status: "SENT",
                totalAmount: 1000,
                expectedDelivery: "2026-08-30",
                items: [],
              },
            },
          ],
          pageInfo: {
            hasNextPage: true,
            endCursor: "cursor-1",
          },
        },
      },
      loading: false,
      error: undefined,
      fetchMore: vi.fn(),
      networkStatus: 3,
    } as never);

    render(
      <MemoryRouter>
        <Orders />
      </MemoryRouter>
    );

    const loadMoreButton = screen.getByRole("button", {
      name: "Loading...",
    });

    expect(loadMoreButton).toBeDisabled();
  });
});