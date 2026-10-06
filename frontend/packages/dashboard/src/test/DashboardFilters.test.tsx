import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import DashboardFilters from "../components/DashboardFilters";
import type { InventoryItem } from "../types/forecast";


const mockInventory: InventoryItem[] = [
  {
    sku_id: "SKU001",
    product_name: "Apples",
    category: "Food",
    warehouse_id: "WH001",
    quantity_on_hand: 120,
    reorder_point: 50,
    needs_reorder: false,
    avg_daily_demand: 10,
  },
  {
    sku_id: "SKU002",
    product_name: "Milk",
    category: "Food",
    warehouse_id: "WH002",
    quantity_on_hand: 50,
    reorder_point: 20,
    needs_reorder: false,
    avg_daily_demand: 5,
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
];

const defaultFilters = {
  warehouse: "All",
  category: "All",
  startDate: "",
  endDate: "",
};

describe("DashboardFilters", () => {
  const onFilterChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    window.history.pushState({}, "", "/");
  });

  it("renders filters", async () => {
    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    expect(
      screen.getByLabelText("Warehouse filter"),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Category filter"),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Start date"),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("End date"),
    ).toBeInTheDocument();
  });

  it("shows readable labels on the triggers by default", () => {
    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    expect(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    ).toHaveTextContent("All Warehouses");

    expect(
      screen.getByRole("combobox", {
        name: "Category filter",
      }),
    ).toHaveTextContent("All Categories");
  });

  it("loads warehouse and category options", async () => {
    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    const warehouseFilter = screen.getByRole("combobox", {
      name: "Warehouse filter",
    });

    await user.click(warehouseFilter);

    expect(
      await screen.findByRole("option", {
        name: "WH001",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("option", {
        name: "WH002",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("option", {
        name: "WH003",
      }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("combobox", {
        name: "Category filter",
      }),
    );

    expect(
      await screen.findByRole("option", {
        name: "Food",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("option", {
        name: "Personal Care",
      }),
    ).toBeInTheDocument();
  });

  it("changes warehouse", async() => {
    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    await user.click(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    );

    await user.click(
      await screen.findByRole("option", {
        name: "WH001",
      }),
    );

    await waitFor(() => {
      expect(onFilterChange).toHaveBeenCalledWith({
        warehouse: "WH001",
        category: "All",
        startDate: "",
        endDate: "",
      });
    });
  });

  it("changes category", async () => {
    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    await user.click(
      screen.getByRole("combobox", {
        name: "Category filter",
      }),
    );

    await user.click(
      await screen.findByRole("option", {
        name: "Food",
      }),
    );

    await waitFor(() => {
      expect(onFilterChange).toHaveBeenCalledWith({
        warehouse: "All",
        category: "Food",
        startDate: "",
        endDate: "",
      });
    });
  });

  it("changes start date", async () => {
    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );


    fireEvent.change(
      screen.getByLabelText("Start date"),
      {
        target: {
          value: "2026-08-01",
        },
      },
    );

    await waitFor(() => {
      expect(onFilterChange).toHaveBeenCalledWith({
        warehouse: "All",
        category: "All",
        startDate: "2026-08-01",
        endDate: "",
      });
    });
  });

  it("changes end date", async () => {
    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );


    fireEvent.change(
      screen.getByLabelText("End date"),
      {
        target: {
          value: "2026-08-31",
        },
      },
    );

    await waitFor(() => {
      expect(onFilterChange).toHaveBeenCalledWith({
        warehouse: "All",
        category: "All",
        startDate: "",
        endDate: "2026-08-31",
      });
    });
  });

  it("updates URL", async () => {
    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    await user.click(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    );

    await user.click(
      await screen.findByRole("option", {
        name: "WH001",
      }),
    );

    await waitFor(() => {
      expect(window.location.search).toBe(
        "?warehouse=WH001",
      );
    });
  });

  it("reads filters from URL", () => {
    window.history.pushState(
      {},
      "",
      "/?warehouse=WH001&category=Food&startDate=2026-08-01&endDate=2026-08-31",
    );

    const urlFilters = {
      warehouse: "WH001",
      category: "Food",
      startDate: "2026-08-01",
      endDate: "2026-08-31",
    };

    render(
      <DashboardFilters
        filters={urlFilters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    expect(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    ).toHaveTextContent("WH001");

    expect(
      screen.getByRole("combobox", {
        name: "Category filter",
      }),
    ).toHaveTextContent("Food");

    expect(
      screen.getByLabelText("Start date"),
    ).toHaveValue("2026-08-01");

    expect(
      screen.getByLabelText("End date"),
    ).toHaveValue("2026-08-31");
  });

  it("removes warehouse from URL when All is selected", async () => {
    window.history.pushState(
      {},
      "",
      "/?warehouse=WH001",
    );

    const filters = {
      warehouse: "WH001",
      category: "All",
      startDate: "",
      endDate: "",
    };

    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={filters}
        onFilterChange={onFilterChange}
        inventory={mockInventory}
      />,
    );

    await user.click(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    );

    await user.click(
      await screen.findByRole("option", {
        name: "All Warehouses",
      }),
    );

    await waitFor(() => {
      expect(window.location.search).toBe("");
    });
  });

  it("handles inventory error", async () => {

    const user = userEvent.setup();

    render(
      <DashboardFilters
        filters={defaultFilters}
        onFilterChange={onFilterChange}
        inventory={[]}
      />,
    );


    await user.click(
      screen.getByRole("combobox", {
        name: "Warehouse filter",
      }),
    );
    expect(
      await screen.findByRole("option", {
      name: "All Warehouses",
    }),
  ).toBeInTheDocument();

    expect(
      screen.queryByRole("option", {
        name: "WH001",
      }),
    ).not.toBeInTheDocument();
  });
});