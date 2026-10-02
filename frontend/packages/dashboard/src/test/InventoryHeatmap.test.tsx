import { fireEvent, render, screen} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InventoryHeatmap from "../components/InventoryHeatmap";
import { inventory } from "../mocks/inventory";


describe("InventoryHeatmap", () => {
  it("shows loading skeleton while inventory is loading", () => {
    render(<InventoryHeatmap data={[]} loading />);
    expect(
      screen.queryByText("Loading Inventory Heatmap...")
    ).not.toBeInTheDocument();
  });

  it("shows error state when inventory loading fails", async () => {
    const onRetry = vi.fn();

    render(
      <InventoryHeatmap
        data={[]}
        error
        onRetry={onRetry}
       />
    );

    expect(
      screen.getByText("Failed to load inventory data.")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Retry" })
    ).toBeInTheDocument();
  });

  it("shows warehouse names after loading", async () => {
    render(<InventoryHeatmap data={inventory} />);

    expect(screen.getByText("WH001")).toBeInTheDocument();
    expect(screen.getByText("WH002")).toBeInTheDocument();
    expect(screen.getByText("WH003")).toBeInTheDocument();
    expect(screen.getByText("WH004")).toBeInTheDocument();
  });

  it("shows inventory products after loading", async () => {
    render(<InventoryHeatmap data={inventory} />);
    expect(
      screen.getByText(inventory[0].sku_id)
    ).toBeInTheDocument();
  });

  it("shows correct stock status", async () => {
    render(<InventoryHeatmap data={inventory} />);

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

  it("shows days remaining on hover", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];

    const daysRemaining =
      item.avg_daily_demand > 0
        ? Math.ceil(
            item.quantity_on_hand /
              item.avg_daily_demand
          )
        : 0;

    const sku = screen.getByText(item.sku_id);

    fireEvent.mouseEnter(sku.parentElement!);

    expect(
      screen.getByText(
        `Days Remaining: ${daysRemaining}`
      )
    ).toBeInTheDocument();

    
  });

  it("renders only a small window of rows from a 10k+ dataset (virtualization)", async () => {
   render(<InventoryHeatmap data={inventory} />);
   // The dataset really is large...
   expect(inventory.length).toBeGreaterThanOrEqual(10000);

   // ...but only a small window of item rows is in the DOM.
   // Each row is a button whose accessible name starts with "SKU ".
   const renderedRows = screen.getAllByRole("button", { name: /^SKU / });

   expect(renderedRows.length).toBeGreaterThan(0);
   expect(renderedRows.length).toBeLessThan(500);

   expect(screen.getByText(inventory[0].sku_id)).toBeInTheDocument();
 });

  it("shows product details on hover", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);

    fireEvent.mouseEnter(sku.parentElement!);

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)).toBeInTheDocument();

    expect(
      screen.getByText(
        `Product: ${item.product_name}`)).toBeInTheDocument();

    expect(
      screen.getByText(
        `Stock: ${item.quantity_on_hand}`)).toBeInTheDocument();

    expect(
      screen.getByText(
        `Reorder Point: ${item.reorder_point}`)).toBeInTheDocument();
  });

  it("makes inventory items keyboard accessible", async () => {
    render(<InventoryHeatmap data={inventory} />);
    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);
    const row = sku.parentElement!;

    expect(row).toHaveAttribute("role", "button");
    expect(row).toHaveAttribute("tabindex", "0");
    expect(row).toHaveAttribute(
      "aria-label",
      `SKU ${item.sku_id}, ${item.product_name}, stock ${item.quantity_on_hand}, reorder point ${item.reorder_point}`
    );
  });

  it("shows product details when an inventory item receives focus", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);
    const row = sku.parentElement!;

    fireEvent.focus(row);

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)).toBeInTheDocument();

    expect(
      screen.getByText(`Product: ${item.product_name}`)).toBeInTheDocument();
  });

  it("shows product details when Enter is pressed on an inventory item", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);
    const row = sku.parentElement!;

    fireEvent.keyDown(row, {
      key: "Enter",
    });

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)).toBeInTheDocument();
  });

  it("shows product details when Space is pressed on an inventory item", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];
    const sku = screen.getByText(item.sku_id);
    const row = sku.parentElement!;

    fireEvent.keyDown(row, {
      key: " ",
    });

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)).toBeInTheDocument();
  });

  it("hides product details when Escape is pressed", async () => {
    render(<InventoryHeatmap data={inventory} />);

    const item = inventory[0];

    const sku = screen.getByText(item.sku_id);
    const row = sku.parentElement!;

    fireEvent.focus(row);

    expect(
      screen.getByText(`SKU: ${item.sku_id}`)).toBeInTheDocument();

    fireEvent.keyDown(row, {
      key: "Escape",
    });

    expect(
      screen.queryByText(`SKU: ${item.sku_id}`)).not.toBeInTheDocument();
  });
});

