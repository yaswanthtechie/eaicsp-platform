import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

const mockShipmentStatus = {
  total: 100,
  pending: 20,
  delivered: 50,
  in_transit: 15,
  delayed: 10,
  cancelled: 5,
};

describe("ShipmentStatus", () => {
  const defaultProps = {
    shipmentStatus: mockShipmentStatus,
    loading: false,
    error: false,
    onRetry: vi.fn(),
  };

  it("shows loading skeleton while loading", () => {
    render(
      <ShipmentStatus
        {...defaultProps}
        loading={true}
      />
    );

    expect(screen.getAllByTestId("skeleton")).toHaveLength(10);
  });

  it("shows shipment status after loading", () => {
    render(<ShipmentStatus {...defaultProps} />);

    expect(screen.getByText("Shipment Status")).toBeInTheDocument();
    expect(
      screen.getByText("Current shipment and logistics status")
    ).toBeInTheDocument();
  });

  it("shows all shipment status labels", () => {
    render(<ShipmentStatus {...defaultProps} />);

    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("In Transit")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Delayed")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows delivery progress", () => {
    render(<ShipmentStatus {...defaultProps} />);

    expect(screen.getByText("Delivery progress")).toBeInTheDocument();
  });

  it("shows shipment counts from mock data", () => {
    render(<ShipmentStatus {...defaultProps} />);

    expect(screen.getByText(/Total shipments:/)).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("In Transit")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Delayed")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("shows delivery percentage after loading", () => {
    render(<ShipmentStatus {...defaultProps} />);

    expect(screen.getAllByText(/\d+%/).length).toBeGreaterThan(0);
  });

  it("shows empty state when shipment data is unavailable", () => {
    render(
      <ShipmentStatus
        {...defaultProps}
        shipmentStatus={undefined}
      />
    );

    expect(
      screen.getByText("No shipment status data available."),
    ).toBeInTheDocument();
  });
});

