import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import InventoryHealth from "../components/InventoryHealth";

interface InventoryItem {
  sku_id: string;
  product_name: string;
  category: string;
  warehouse_id: string;
  quantity_on_hand: number;
  reorder_point: number;
  needs_reorder: boolean;
  avg_daily_demand: number;
}

const mockInventory: InventoryItem[] = [
  {
    sku_id: "SKU-000010",
    product_name: "Lumina Glass Cleaner - 1 L",
    category: "Cleaning",
    warehouse_id: "WH-BOM-01",
    quantity_on_hand: 60,
    reorder_point: 30,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000011",
    product_name: "Kestrel Hi-Vis Vest - Pack of 10",
    category: "Safety",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 110,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000012",
    product_name: "Brightline Bubble Wrap - Pack of 100",
    category: "Packaging",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 60,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 8,
  },
  {
    sku_id: "SKU-000013",
    product_name: "Ardent Face Mask - Pack of 10",
    category: "Safety",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 85,
    reorder_point: 40,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU-000014",
    product_name: "Ardent Bubble Wrap - Pack of 100",
    category: "Packaging",
    warehouse_id: "WH-CCU-01",
    quantity_on_hand: 20,
    reorder_point: 40,
    needs_reorder: true,
    avg_daily_demand: 4,
  },
];

const defaultProps = {
  inventory: mockInventory,
  warehouse: "All",
  category: "All",
};

describe("InventoryHealth", () => {

  it("loads and displays inventory health", () => {
    render(<InventoryHealth {...defaultProps} />);

    expect(
      screen.getByText("Inventory Health")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Healthy")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Low Stock")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Critical")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Need Reorder")
    ).toBeInTheDocument();
  });

  it("calculates and displays health counts", () => {
    render(<InventoryHealth {...defaultProps} />);

    const healthyButton = screen.getByRole("button", {
      name: /Healthy/i,
    });

    const lowStockButton = screen.getByRole("button", {
      name: /Low Stock/i,
    });

    const criticalButton = screen.getByRole("button", {
      name: /Critical/i,
    });

    const reorderButton = screen.getByRole("button", {
      name: /Need Reorder/i,
    });

    expect(healthyButton).toHaveTextContent("1");
    expect(lowStockButton).toHaveTextContent("3");
    expect(criticalButton).toHaveTextContent("1");
    expect(reorderButton).toHaveTextContent("1");
  });

  it("filters healthy inventory", () => {
    render(<InventoryHealth {...defaultProps} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Healthy/i,
      })
    );

    expect(
      screen.getByText("Healthy Inventory")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Kestrel Hi-Vis Vest - Pack of 10")
    ).toBeInTheDocument();

    expect(
      screen.getByText("11.0 days")
    ).toBeInTheDocument();
  });

  it("filters low stock inventory", () => {
    render(<InventoryHealth {...defaultProps} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Low Stock/i,
      })
    );

    expect(
      screen.getByText("Low Inventory")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Lumina Glass Cleaner - 1 L")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Brightline Bubble Wrap - Pack of 100")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Ardent Face Mask - Pack of 10")
    ).toBeInTheDocument();

    expect(
      screen.getByText("6.0 days")
    ).toBeInTheDocument();

    expect(
      screen.getByText("8.0 days")
    ).toBeInTheDocument();

    expect(
      screen.getByText("9.0 days")
    ).toBeInTheDocument();
  });

  it("filters critical inventory", () => {
    render(<InventoryHealth {...defaultProps} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Critical/i,
      })
    );

    expect(
      screen.getByText("Critical Inventory")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Ardent Bubble Wrap - Pack of 100")
    ).toBeInTheDocument();

    expect(
      screen.getByText("5.0 days")
    ).toBeInTheDocument();
  });

  it("filters reorder inventory", () => {
    render(<InventoryHealth {...defaultProps} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Need Reorder/i,
      })
    );

    expect(
      screen.getByText("Items Needing Reorder")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Ardent Bubble Wrap - Pack of 100")
    ).toBeInTheDocument();

    expect(
      screen.getByText("5.0 days")
    ).toBeInTheDocument();
  });

  it("clears the active filter", () => {
    render(<InventoryHealth {...defaultProps} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /Critical/i,
      })
    );

    expect(
      screen.getByText("Critical Inventory")
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Clear",
      })
    );

    expect(
      screen.queryByText("Critical Inventory")
    ).not.toBeInTheDocument();
  });

  it("toggles the active filter off", () => {
    render(<InventoryHealth {...defaultProps} />);

    const healthyButton = screen.getByRole("button", {
      name: /Healthy/i,
    });

    fireEvent.click(healthyButton);

    expect(
      screen.getByText("Healthy Inventory")
    ).toBeInTheDocument();

    fireEvent.click(healthyButton);

    expect(
      screen.queryByText("Healthy Inventory")
    ).not.toBeInTheDocument();
  });

  it("shows empty state when no items match the filter", () => {
    const inventoryWithoutReorder: InventoryItem[] = [
      {
        sku_id: "SKU-000012",
        product_name: "Brightline Bubble Wrap - Pack of 100",
        category: "Packaging",
        warehouse_id: "WH-CCU-01",
        quantity_on_hand: 60,
        reorder_point: 50,
        needs_reorder: false,
        avg_daily_demand: 8,
      },
    ];

    render(
      <InventoryHealth
        inventory={inventoryWithoutReorder}
        warehouse="All"
        category="All"
      />
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /Need Reorder/i,
      })
    );

    expect(
      screen.getByText("Items Needing Reorder")
    ).toBeInTheDocument();

    expect(
      screen.getByText("No inventory items found.")
    ).toBeInTheDocument();
  });

  it("displays product and warehouse names with their IDs", () => {
    render(
      <InventoryHealth
        {...defaultProps}
        productNames={{
          "SKU-000010": "Lumina Glass Cleaner - 500 ml 10",
        }}
        warehouseNames={{
          "WH-BOM-01": "Mumbai Central DC",
        }}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
      name: /Low Stock/i,
    }),
  );

    expect(
      screen.getByText("Lumina Glass Cleaner - 500 ml 10 (SKU-000010)"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Mumbai Central DC (WH-BOM-01)"),
    ).toBeInTheDocument();
  });

  it("falls back to the product name and warehouse ID when names are missing", () => {
    render(
      <InventoryHealth
        {...defaultProps}
        productNames={{}}
        warehouseNames={{}}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
      name: /Low Stock/i,
    }),
  );

    expect(
      screen.getByText("Lumina Glass Cleaner - 1 L"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("WH-BOM-01"),
    ).toBeInTheDocument();
  });
});
