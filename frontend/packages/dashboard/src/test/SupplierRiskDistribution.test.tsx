import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SupplierRiskDistribution from "../components/SupplierRiskDistribution";

vi.mock("../components/Skeleton", () => ({
  default: ({
    width,
    height,
  }: {
    width: string;
    height: number;
  }) => (
    <div data-testid="skeleton">
      {width}-{height}
    </div>
  ),
}));

describe("SupplierRiskDistribution", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows loading skeleton while loading", () => {
    render(<SupplierRiskDistribution />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(2);
  });

  it("shows chart title after loading", async () => {
    render(<SupplierRiskDistribution />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(
      screen.getByText("Supplier Risk Distribution")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Suppliers grouped by risk score")
    ).toBeInTheDocument();
  });

  it("renders chart after loading", async () => {
    render(<SupplierRiskDistribution />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(
      screen.getByText("Supplier Risk Distribution")
    ).toBeInTheDocument();
  });
});