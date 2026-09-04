import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import InventoryTable from "./InventoryTable";

afterEach(() => {
  cleanup();
});

describe("InventoryTable", () => {
  it("shows the inventory after loading", async () => {
    render(<InventoryTable />);

    await waitFor(
      () => {
        expect(screen.getByText("SKU001")).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it("searches inventory by SKU", async () => {
    render(<InventoryTable />);

    await waitFor(
      () => {
        expect(screen.getByText("SKU001")).toBeInTheDocument();
      },
      { timeout: 2000 }
    );

    const searchInput =
      screen.getByPlaceholderText("Search SKU...");

    fireEvent.change(searchInput, {
      target: {
        value: "SKU001",
      },
    });

    expect(screen.getByText("SKU001")).toBeInTheDocument();
  });

  it("filters low stock items", async () => {
    render(<InventoryTable />);

    await waitFor(
      () => {
        expect(screen.getByText("SKU001")).toBeInTheDocument();
      },
      { timeout: 2000 }
    );

    const checkbox = screen.getByRole("checkbox");

    fireEvent.click(checkbox);

    expect(checkbox).toBeChecked();

    await waitFor(() => {
      expect(
        screen.getAllByText("Low Stock").length
      ).toBeGreaterThan(0);
    });
  });

  it("shows empty message when SKU is not found", async () => {
    render(<InventoryTable />);

    await waitFor(
      () => {
        expect(screen.getByText("SKU001")).toBeInTheDocument();
      },
      { timeout: 2000 }
    );

    const searchInput =
      screen.getByPlaceholderText("Search SKU...");

    fireEvent.change(searchInput, {
      target: {
        value: "NOTFOUND",
      },
    });

    expect(
      screen.getByText("SKU Number Not Available")
    ).toBeInTheDocument();
  });
});
