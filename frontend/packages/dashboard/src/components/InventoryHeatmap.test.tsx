import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { act } from "react";
import InventoryHeatmap from "./InventoryHeatmap";
import { inventory } from "../mocks/inventory";

vi.mock("../../../ui/src/components/Badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("InventoryHeatmap", () => {
  it("shows loading state", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    expect(
      screen.getByText("Loading Inventory Heatmap...")
    ).toBeInTheDocument();
  });

  it("shows warehouse names after loading", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("WH001")).toBeInTheDocument();
    expect(screen.getByText("WH002")).toBeInTheDocument();
    expect(screen.getByText("WH003")).toBeInTheDocument();
  });

  it("shows inventory products after loading", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(
      screen.getByText(inventory[0].sku_id)
    ).toBeInTheDocument();
  });

  it("shows correct stock status", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getAllByText("Low Stock").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Near Reorder").length).toBeGreaterThan(0);
  });

  it("shows product details on hover", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);

    fireEvent.mouseEnter(sku.parentElement!);

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)
    ).toBeInTheDocument();

    expect(
      screen.getByText(`Product: ${item.product_name}`)
    ).toBeInTheDocument();

    expect(
      screen.getByText(`Quantity: ${item.quantity_on_hand}`)
    ).toBeInTheDocument();

    expect(
      screen.getByText(`Reorder Point: ${item.reorder_point}`)
    ).toBeInTheDocument();
  });
});