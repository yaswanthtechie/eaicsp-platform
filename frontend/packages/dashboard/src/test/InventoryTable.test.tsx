import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import InventoryTable from "../components/InventoryTable";
import { inventory } from "../mocks/inventory";

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


  it("shows loading skeleton while inventory is loading", () => {
    render(<InventoryTable data={[]} loading />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(4);
  });

  it("shows the inventory after loading", () => {
    render(<InventoryTable data={inventory} />);

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

  it("searches inventory by SKU", () => {
    render(<InventoryTable data={inventory} />);

    const searchInput = screen.getByPlaceholderText("Search SKU");

    fireEvent.change(searchInput, {
      target: {
        value: "SKU001",
      },
    });

    expect(searchInput).toHaveValue("SKU001");
  });

  it("filters low stock items", () => {
    render(<InventoryTable data={inventory} />);

    const checkbox = screen.getByRole("checkbox", {
      name: "Show only low stock items"
    });

    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);

    expect(checkbox).toBeChecked();
  });

  it("shows empty message when SKU is not found", () => {
    render(<InventoryTable data={inventory} />);

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

  it("shows days remaining and expected order date", () => {
    render(<InventoryTable data={inventory} />);

    expect(
      screen.getByText("Days Remaining")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Expected Order Date")
    ).toBeInTheDocument();
  });


  it("has accessible loading state", () => {
    render(<InventoryTable data={[]} loading />);

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

  it("has an accessible search input", () => {
    render(<InventoryTable data={inventory} />);

    const searchInput = screen.getByLabelText(
      "Search inventory items by SKU No"
    );

    expect(searchInput).toBeInTheDocument();
    expect(searchInput).toHaveAttribute("id","inventory-search");
  });

  it("has an accessible low stock checkbox", () => {
    render(<InventoryTable data={inventory} />);

    const checkbox = screen.getByRole("checkbox", {
      name: "Show only low stock items"
    });

    expect(checkbox).toBeInTheDocument();
  });

  it("has accessible table structure", () => {
    render(<InventoryTable data={inventory} />);

    const table = screen.getByRole("table", {
      name: "Inventory items",
    });

    expect(table).toBeInTheDocument();

    expect(
      screen.getAllByRole("columnheader")
    ).toHaveLength(9);

    expect(screen.getAllByRole("row").length).toBeGreaterThan(0);
  });

  it("has accessible table cells", () => {
    render(<InventoryTable data={inventory} />);

    expect(
      screen.getAllByRole("cell").length
    ).toBeGreaterThan(0);
  });

  it("shows accessible error state with retry button", () => {
    const onRetry = vi.fn();

    render(
      <InventoryTable
        data={[]}
        error
        onRetry={onRetry}
      />,
    );

    const alert = screen.getByRole("alert");

    expect(alert).toBeInTheDocument();

    const retryButton = screen.getByRole("button", {
      name: "Retry",
    });

    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

