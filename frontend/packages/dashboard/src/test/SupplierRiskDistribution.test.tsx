import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SupplierRiskDistribution from "../components/SupplierRiskDistribution";
import { supplierRisk } from "../mocks/supplierRisk";

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

  it("shows loading skeleton while loading", () => {
    render(
      <SupplierRiskDistribution
        supplierRisk={supplierRisk}
        loading
        error={false}
        onRetry={() => {}}
      />,
    );

    expect(screen.getAllByTestId("skeleton")).toHaveLength(2);
  });

  it("shows chart title after loading", () => {
    render(
      <SupplierRiskDistribution
        supplierRisk={supplierRisk}
        loading={false}
        error={false}
        onRetry={() => {}}
      />,
    );

    expect(
      screen.getByText("Supplier Risk Distribution")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Suppliers grouped by risk score")
    ).toBeInTheDocument();
  });

  it("renders chart after loading", () => {
    render(
      <SupplierRiskDistribution
        supplierRisk={supplierRisk}
        loading={false}
        error={false}
        onRetry={() => {}}
      />,
    );

    expect(
      screen.getByText("Supplier Risk Distribution")
    ).toBeInTheDocument();
  });

  it("has accessible loading state", () => {
    render(
      <SupplierRiskDistribution
        supplierRisk={supplierRisk}
        loading
        error={false}
        onRetry={() => {}}
      />,
    );

    const loadingState = screen.getByRole("status");

    expect(loadingState).toHaveAttribute(
      "aria-busy",
      "true"
    );

    expect(loadingState).toHaveAttribute(
      "aria-label",
      "Loading supplier risk distribution"
    );
  });

  it("shows error state with retry button", () => {
    const onRetry = vi.fn();

    render(
      <SupplierRiskDistribution
        supplierRisk={supplierRisk}
        loading={false}
        error
        onRetry={onRetry}
      />,
    );

  const retryButton = screen.getByRole("button", {
    name: "Retry",
  });

  expect(retryButton).toBeInTheDocument();

  fireEvent.click(retryButton);

  expect(onRetry).toHaveBeenCalledTimes(1);
});

it("has an accessible chart name", () => {
  render(
    <SupplierRiskDistribution
      supplierRisk={supplierRisk}
      loading={false}
      error={false}
      onRetry={() => {}}
    />,
  );

  const chart = screen.getByRole("img", {
    name: /Supplier risk distribution chart/i,
  });
  expect(chart).toBeInTheDocument();
  expect(chart).toHaveAttribute("role","img");
  });
});