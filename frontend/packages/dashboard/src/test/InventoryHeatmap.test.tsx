import { cleanup, fireEvent, render, screen} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";

import InventoryHeatmap from "../components/InventoryHeatmap";
import { inventory } from "../mocks/inventory";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("InventoryHeatmap", () => {
  it("shows loading skeleton while inventory is loading", () => {
    vi.useFakeTimers();

    const { container } = render(<InventoryHeatmap />);

    expect(
      screen.queryByText("WH001")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Loading Inventory Heatmap...")
    ).not.toBeInTheDocument();

    expect(
      container.querySelectorAll("div").length
    ).toBeGreaterThan(1);
  });

  it("shows error state when inventory loading fails", async () => {
    vi.useFakeTimers();

    render(<InventoryHeatmap shouldFail />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(
      screen.getByText("Failed to load inventory data.")
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
      screen.getAllByText("Healthy").length
    ).toBeGreaterThan(0);

    expect(
      screen.getAllByText("Low Soon").length
    ).toBeGreaterThan(0);

    expect(
      screen.getAllByText("Needs Reorder").length
    ).toBeGreaterThan(0);
  });

  it("shows days remaining and expected order date on hover", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-09"));

    render(<InventoryHeatmap />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    const item = inventory[0];

    const daysRemaining =
      item.avg_daily_demand > 0
        ? Math.ceil(
            item.quantity_on_hand /
              item.avg_daily_demand
          )
        : 0;

    const expectedOrderDate = new Date("2026-09-09");

    expectedOrderDate.setHours(0, 0, 0, 0);
    expectedOrderDate.setDate(
      expectedOrderDate.getDate() + daysRemaining
    );

    const formattedOrderDate =
      expectedOrderDate.toLocaleDateString("en-GB");

    const sku = screen.getByText(item.sku_id);

    fireEvent.mouseEnter(sku.parentElement!);

    expect(
      screen.getByText(
        `Days Remaining: ${daysRemaining}`
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        `Expected Order: ${formattedOrderDate}`
      )
    ).toBeInTheDocument();
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
      screen.getByText(
        `Product: ${item.product_name}`
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        `Stock: ${item.quantity_on_hand}`
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        `Reorder Point: ${item.reorder_point}`
      )
    ).toBeInTheDocument();
  });
});

