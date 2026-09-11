import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardFilters from "../components/DashboardFilters";
import { loadInventory } from "../mocks/inventory";
import type { InventoryItem } from "../types/forecast";

vi.mock("../mocks/inventory", () => ({
  loadInventory: vi.fn(),
}));

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

describe("DashboardFilters", () => {
  const onFilterChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    window.history.pushState({}, "", "/");

    vi.mocked(loadInventory).mockResolvedValue(mockInventory);
  });

  it("renders filters", async () => {
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
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

    await waitFor(() => {
      expect(loadInventory).toHaveBeenCalled();
    });
  });

  it("shows default values", async () => {
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByLabelText("Warehouse filter"),
      ).toHaveValue("All");

      expect(
        screen.getByLabelText("Category filter"),
      ).toHaveValue("All");
    });
  });

  it("loads warehouse and category options", async () => {
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "WH001",
        }),
      ).toBeInTheDocument();

      expect(
        screen.getByRole("option", {
          name: "WH002",
        }),
      ).toBeInTheDocument();

      expect(
        screen.getByRole("option", {
          name: "WH003",
        }),
      ).toBeInTheDocument();

      expect(
        screen.getByRole("option", {
          name: "Food",
        }),
      ).toBeInTheDocument();

      expect(
        screen.getByRole("option", {
          name: "Personal Care",
        }),
      ).toBeInTheDocument();
    });
  });

  it("changes warehouse", async () => {
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "WH001",
        }),
      ).toBeInTheDocument();
    });

    fireEvent.change(
      screen.getByLabelText("Warehouse filter"),
      {
        target: {
          value: "WH001",
        },
      },
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
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "Food",
        }),
      ).toBeInTheDocument();
    });

    fireEvent.change(
      screen.getByLabelText("Category filter"),
      {
        target: {
          value: "Food",
        },
      },
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
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(loadInventory).toHaveBeenCalled();
    });

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
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(loadInventory).toHaveBeenCalled();
    });

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
    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "WH001",
        }),
      ).toBeInTheDocument();
    });

    fireEvent.change(
      screen.getByLabelText("Warehouse filter"),
      {
        target: {
          value: "WH001",
        },
      },
    );

    await waitFor(() => {
      expect(window.location.search).toBe(
        "?warehouse=WH001",
      );
    });
  });

  it("reads filters from URL", async () => {
    window.history.pushState(
      {},
      "",
      "/?warehouse=WH001&category=Food&startDate=2026-08-01&endDate=2026-08-31",
    );

    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByLabelText("Warehouse filter"),
      ).toHaveValue("WH001");

      expect(
        screen.getByLabelText("Category filter"),
      ).toHaveValue("Food");

      expect(
        screen.getByLabelText("Start date"),
      ).toHaveValue("2026-08-01");

      expect(
        screen.getByLabelText("End date"),
      ).toHaveValue("2026-08-31");
    });
  });

  it("removes warehouse from URL when All is selected", async () => {
    window.history.pushState(
      {},
      "",
      "/?warehouse=WH001",
    );

    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "WH001",
        }),
      ).toBeInTheDocument();
    });

    fireEvent.change(
      screen.getByLabelText("Warehouse filter"),
      {
        target: {
          value: "All",
        },
      },
    );

    await waitFor(() => {
      expect(window.location.search).toBe("");
    });
  });

  it("handles inventory error", async () => {
    vi.mocked(loadInventory).mockRejectedValue(
      new Error("Failed"),
    );

    render(
      <DashboardFilters
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("option", {
          name: "All Warehouses",
        }),
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("option", {
        name: "WH001",
      }),
    ).not.toBeInTheDocument();
  });
});
