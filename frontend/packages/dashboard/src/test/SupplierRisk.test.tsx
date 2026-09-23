import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SupplierRisk from "../components/SupplierRisk";

vi.mock("../components/Skeleton", () => ({
  default: ({
    width,
    height,
  }: {
    width: string;
    height: number;
  }) => <div data-testid="skeleton">{width}-{height}</div>,
}));

describe("SupplierRisk", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows loading skeleton while loading", () => {
    render(<SupplierRisk />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(2);
  });

  it("shows supplier risk summary after loading", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("Supplier Risk Summary")).toBeInTheDocument();
    expect(
      screen.getByText("Risk score and model confidence by supplier")
    ).toBeInTheDocument();
  });

  it("shows supplier names", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("BlinkIt")).toBeInTheDocument();
    expect(screen.getByText("DMart")).toBeInTheDocument();
    expect(screen.getByText("Big Basket")).toBeInTheDocument();
    expect(screen.getByText("Wholesale Shop")).toBeInTheDocument();
  });

  it("shows risk levels", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getAllByText("High Risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Medium Risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Low Risk").length).toBeGreaterThan(0);
  });

  it("shows risk score and confidence labels", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getAllByText("Risk Score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Confidence").length).toBeGreaterThan(0);
  });

  it("shows sentiment information", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getAllByText("Sentiment").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Positive/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Negative/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Neutral/).length).toBeGreaterThan(0);
  });

  it("shows percentage values", async () => {
    render(<SupplierRisk />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getAllByText(/\d+%/).length).toBeGreaterThan(0);
  });
});