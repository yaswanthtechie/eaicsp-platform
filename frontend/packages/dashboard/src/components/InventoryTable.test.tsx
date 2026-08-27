import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";

import InventoryTable from "./InventoryTable";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("InventoryTable", () => {
  it("shows the inventory after loading", () => {
    vi.useFakeTimers();

    render(<InventoryTable />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("SKU001")).toBeInTheDocument();
  });

  it("searches inventory by SKU", () => {
    vi.useFakeTimers();

    render(<InventoryTable />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const searchInput =
      screen.getByPlaceholderText("Search SKU...");

    fireEvent.change(searchInput, {
      target: { value: "SKU001" },
    });

    expect(screen.getByText("SKU001")).toBeInTheDocument();
  });

  it("filters low stock items", () => {
    vi.useFakeTimers();

    render(<InventoryTable />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const checkbox = screen.getByRole("checkbox");

    fireEvent.click(checkbox);

    expect(checkbox).toBeChecked();
    expect(screen.getAllByText("Low Stock").length).toBeGreaterThan(0);
  });

  it("shows empty message when SKU is not found", () => {
    vi.useFakeTimers();

    render(<InventoryTable />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const searchInput =
      screen.getByPlaceholderText("Search SKU...");

    fireEvent.change(searchInput, {
      target: { value: "NOTFOUND" },
    });

    expect(
      screen.getByText("SKU Number Not Available")
    ).toBeInTheDocument();
  });
});