import { render, screen, fireEvent, cleanup} from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";

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
    sku_id: "SKU010",
    product_name: "Mango Juice",
    category: "Food",
    warehouse_id: "WH002",
    quantity_on_hand: 60,
    reorder_point: 30,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU011",
    product_name: "Soap",
    category: "Personal Care",
    warehouse_id: "WH003",
    quantity_on_hand: 110,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU012",
    product_name: "Shampoo",
    category: "Personal Care",
    warehouse_id: "WH003",
    quantity_on_hand: 60,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 8,
  },
  {
    sku_id: "SKU013",
    product_name: "Toothpaste",
    category: "Personal Care",
    warehouse_id: "WH003",
    quantity_on_hand: 85,
    reorder_point: 40,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU014",
    product_name: "Detergent",
    category: "Household",
    warehouse_id: "WH003",
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
  afterEach(() => {
    cleanup();
  });

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
      screen.getByText("Soap")
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
      screen.getByText("Mango Juice")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Shampoo")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Toothpaste")
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
      screen.getByText("Detergent")
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
      screen.getByText("Detergent")
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
        sku_id: "SKU012",
        product_name: "Shampoo",
        category: "Personal Care",
        warehouse_id: "WH003",
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
});
