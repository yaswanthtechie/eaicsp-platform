import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ShipmentStatus from "../components/ShipmentStatus";

vi.mock("../components/Skeleton", () => ({
  default: ({
    width,
    height,
  }: {
    width: string;
    height: number;
  }) => <div data-testid="skeleton">{width}-{height}</div>,
}));

describe("ShipmentStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows loading skeleton while loading", () => {
    render(<ShipmentStatus />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(10);
  });

  it("shows shipment status after loading", async () => {
    render(<ShipmentStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("Shipment Status")).toBeInTheDocument();
    expect(
      screen.getByText("Current shipment and logistics status")
    ).toBeInTheDocument();
  });

  it("shows all shipment status labels", async () => {
    render(<ShipmentStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("In Transit")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Delayed")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows delivery progress", async () => {
    render(<ShipmentStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("Delivery progress")).toBeInTheDocument();
  });

  it("shows shipment counts from mock data", async () => {
    render(<ShipmentStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText(/Total shipments:/)).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("In Transit")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Delayed")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows delivery percentage after loading", async () => {
    render(<ShipmentStatus />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getAllByText(/\d+%/).length).toBeGreaterThan(0);
  });
});