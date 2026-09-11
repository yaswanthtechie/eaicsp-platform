import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AlertsPanel from "../components/AlertsPanel";
import type { AlertMessage } from "../types/forecast";

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

const alert: AlertMessage = {
  id: "alert-1",
  type: "low-stock",
  severity: "warning",
  message: "Product ABC is running low.",
  timestamp: "2026-09-10T10:30:00.000Z",
};

const defaultProps = {
  alerts: [alert],
  connected: true,
  isConnecting: false,
  failed: false,
  onRemove: vi.fn(),
};

describe("AlertsPanel", () => {
  it("shows loading skeleton while connecting", () => {
    render(
      <AlertsPanel
        {...defaultProps}
        isConnecting={true}
        alerts={[]}
      />
    );

    expect(screen.getAllByTestId("skeleton")).toHaveLength(5);
  });

  it("shows connected status", () => {
    render(<AlertsPanel {...defaultProps} />);

    expect(screen.getByText("🟢 Connected")).toBeInTheDocument();
  });

  it("shows disconnected status", () => {
    render(
      <AlertsPanel
        {...defaultProps}
        connected={false}
      />
    );

    expect(screen.getByText("🔴 Disconnected")).toBeInTheDocument();
  });

  it("shows connecting status", () => {
    render(
      <AlertsPanel
        {...defaultProps}
        isConnecting={true}
        alerts={[]}
      />
    );

    expect(screen.getAllByTestId("skeleton")).toHaveLength(5);
  });

  it("shows failed connection message", () => {
    render(
      <AlertsPanel
        {...defaultProps}
        failed={true}
        alerts={[]}
      />
    );

    expect(
      screen.getByText("Unable to connect to the alerts service.")
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Connection failed after multiple retry attempts."
      )
    ).toBeInTheDocument();
  });

  it("shows no alerts message when alerts are empty", () => {
    render(
      <AlertsPanel
        {...defaultProps}
        alerts={[]}
      />
    );

    expect(
      screen.getByText("No Alerts Available.")
    ).toBeInTheDocument();
  });

  it("shows a low stock alert", () => {
    render(<AlertsPanel {...defaultProps} />);

    expect(
      screen.getByText("Low Stock Item Alert")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Product ABC is running low.")
    ).toBeInTheDocument();
  });

  it("shows forecast change alert", () => {
    const forecastAlert: AlertMessage = {
      ...alert,
      id: "alert-2",
      type: "forecast-change",
      severity: "info",
      message: "Forecast changed for Product XYZ.",
    };

    render(
      <AlertsPanel
        {...defaultProps}
        alerts={[forecastAlert]}
      />
    );

    expect(
      screen.getByText("Forecast Change")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Forecast changed for Product XYZ.")
    ).toBeInTheDocument();
  });

  it("shows system status alert", () => {
    const systemAlert: AlertMessage = {
      ...alert,
      id: "alert-3",
      type: "system",
      severity: "error",
      message: "System service is unavailable.",
    };

    render(
      <AlertsPanel
        {...defaultProps}
        alerts={[systemAlert]}
      />
    );

    expect(
      screen.getByText("System Status")
    ).toBeInTheDocument();

    expect(
      screen.getByText("System service is unavailable.")
    ).toBeInTheDocument();
  });

  it("removes an alert after 5.5 seconds", () => {
    const onRemove = vi.fn();

    vi.useFakeTimers();

    render(
      <AlertsPanel
        {...defaultProps}
        onRemove={onRemove}
      />
    );

    expect(
      screen.getByText("Product ABC is running low.")
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5500);
    });

    expect(onRemove).toHaveBeenCalledWith("alert-1");

    vi.useRealTimers();
  });
});