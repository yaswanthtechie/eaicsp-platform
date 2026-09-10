import {cleanup, fireEvent, render,screen} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  vi.restoreAllMocks();
});

describe("InventoryHeatmap", () => {
  it("shows loading state", () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    expect(
      screen.getByText("Loading Inventory Heatmap...")
    ).toBeInTheDocument();
  });

  it("shows error state when inventory loading fails", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap shouldFail />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(
      screen.getByText("Something went wrong in Heatmap Data.")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Retry" })
    ).toBeInTheDocument();
  });

  it("shows warehouse names after loading", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("WH001")).toBeInTheDocument();
    expect(screen.getByText("WH002")).toBeInTheDocument();
    expect(screen.getByText("WH003")).toBeInTheDocument();
  });

  it("shows inventory products after loading", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(
      screen.getByText(inventory[0].sku_id)
    ).toBeInTheDocument();
  });

  it("shows correct stock status", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(
      screen.getAllByText("Low Stock").length
    ).toBeGreaterThan(0);

    expect(
      screen.getAllByText("Healthy").length
    ).toBeGreaterThan(0);

    expect(
      screen.getAllByText("Near Reorder").length
    ).toBeGreaterThan(0);
  });

  it("shows product details on hover", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap />);

    await act(async () => {
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