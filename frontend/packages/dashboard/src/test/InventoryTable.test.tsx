import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InventoryTable from "../components/InventoryTable";

vi.mock("../components/Skeleton", () => ({
  default: ({
    width,
    height,
  }: {
    width: string | number;
    height: number;
  }) => (
    <div data-testid="skeleton">
      {width}-{height}
    </div>
  ),
}));

describe("InventoryTable", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function loadTable() {
    render(<InventoryTable />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
  }

  it("shows loading skeleton while inventory is loading", () => {
    render(<InventoryTable />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(4);
  });

  it("shows the inventory after loading", async () => {
    await loadTable();

    expect(screen.getByText("Inventory Table")).toBeInTheDocument();
    expect(screen.getByText("SKU")).toBeInTheDocument();
    expect(screen.getByText("Product")).toBeInTheDocument();
    expect(screen.getByText("Category")).toBeInTheDocument();
    expect(screen.getByText("Warehouse")).toBeInTheDocument();
    expect(screen.getByText("Quantity")).toBeInTheDocument();
    expect(screen.getByText("Reorder Point")).toBeInTheDocument();
    expect(screen.getByText("Days Remaining")).toBeInTheDocument();
    expect(
      screen.getByText("Expected Order Date")
    ).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("searches inventory by SKU", async () => {
    await loadTable();

    const searchInput = screen.getByPlaceholderText("Search SKU");

    fireEvent.change(searchInput, {
      target: {
        value: "SKU001",
      },
    });

    expect(searchInput).toHaveValue("SKU001");
  });

  it("filters low stock items", async () => {
    await loadTable();

    const checkbox = screen.getByLabelText(
      "Show only low stock items"
    );

    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);

    expect(checkbox).toBeChecked();
  });

  it("shows empty message when SKU is not found", async () => {
    await loadTable();

    const searchInput = screen.getByPlaceholderText("Search SKU");

    fireEvent.change(searchInput, {
      target: {
        value: "NOT-AVAILABLE-SKU",
      },
    });

    expect(
      screen.getByText("SKU Number Not Available")
    ).toBeInTheDocument();
  });

  it("shows days remaining and expected order date", async () => {
    await loadTable();

    expect(
      screen.getByText("Days Remaining")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Expected Order Date")
    ).toBeInTheDocument();
  });

  
  it("has accessible loading state", () => {
    render(<InventoryTable />);

    const loadingContainer = screen.getByRole("status");

    expect(loadingContainer).toHaveAttribute(
      "aria-busy",
      "true"
    );

    expect(loadingContainer).toHaveAttribute(
      "aria-label",
      "Loading inventory table"
    );
  });

  it("has an accessible search input", async () => {
    await loadTable();

    const searchInput = screen.getByLabelText(
      "Search inventory by SKU"
    );

    expect(searchInput).toBeInTheDocument();
    expect(searchInput).toHaveAttribute("id","inventory-search");
  });

  it("has an accessible low stock checkbox", async () => {
    await loadTable();

    const checkbox = screen.getByLabelText(
      "Show only low stock items"
    );

    expect(checkbox).toBeInTheDocument();
    expect(checkbox).toHaveAttribute("type", "checkbox");
  });

  it("has accessible table structure", async () => {
    await loadTable();

    const table = screen.getByRole("table", {
      name: "Inventory items",
    });

    expect(table).toBeInTheDocument();

    expect(
      screen.getAllByRole("columnheader")
    ).toHaveLength(9);

    expect(screen.getAllByRole("row").length).toBeGreaterThan(0);
  });

  it("has accessible table cells", async () => {
    await loadTable();

    expect(
      screen.getAllByRole("cell").length
    ).toBeGreaterThan(0);
  });

  it("shows accessible error state with retry button", async () => {
    render(<InventoryTable shouldFail />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    const alert = screen.getByRole("alert");

    expect(alert).toBeInTheDocument();

    const retryButton = screen.getByRole("button", {
      name: "Retry",
    });

    expect(retryButton).toBeInTheDocument();
  });

});