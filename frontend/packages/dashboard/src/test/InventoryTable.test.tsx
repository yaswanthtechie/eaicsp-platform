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
});