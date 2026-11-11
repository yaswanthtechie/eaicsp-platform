import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AlertsPanel from "../components/AlertsPanel";
import type { AlertMessage } from "../types/forecast";

vi.mock("../components/Skeleton", () => ({
  default: ({ width, height }: { width: string; height: number }) => (
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
    render(<AlertsPanel {...defaultProps} isConnecting={true} alerts={[]} />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(5);
  });

  it("shows connected status", () => {
    render(<AlertsPanel {...defaultProps} />);

    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows disconnected status", () => {
    render(<AlertsPanel {...defaultProps} connected={false} />);

    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("shows connecting status", () => {
    render(<AlertsPanel {...defaultProps} isConnecting={true} alerts={[]} />);

    expect(screen.getAllByTestId("skeleton")).toHaveLength(5);
  });

  it("shows failed connection message", () => {
    render(<AlertsPanel {...defaultProps} failed={true} alerts={[]} />);

    expect(
      screen.getByText("Unable to connect to the alerts service."),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Connection failed after multiple retry attempts."),
    ).toBeInTheDocument();
  });

  it("shows no alerts message when alerts are empty", () => {
    render(<AlertsPanel {...defaultProps} alerts={[]} />);

    expect(screen.getByText("No Alerts Available.")).toBeInTheDocument();
  });

  it("shows a low stock alert", () => {
    render(<AlertsPanel {...defaultProps} />);

    expect(screen.getByText("Low Stock Item Alert")).toBeInTheDocument();

    expect(screen.getByText("Product ABC is running low.")).toBeInTheDocument();
  });

  it("shows forecast change alert", () => {
    const forecastAlert: AlertMessage = {
      ...alert,
      id: "alert-2",
      type: "forecast-change",
      severity: "info",
      message: "Forecast changed for Product XYZ.",
    };

    render(<AlertsPanel {...defaultProps} alerts={[forecastAlert]} />);

    expect(screen.getByText("Forecast Change")).toBeInTheDocument();

    expect(
      screen.getByText("Forecast changed for Product XYZ."),
    ).toBeInTheDocument();
  });

  it("shows system status alert", () => {
    const systemAlert: AlertMessage = {
      ...alert,
      id: "alert-3",
      type: "system",
      severity: "critical",
      message: "System service is unavailable.",
    };

    render(<AlertsPanel {...defaultProps} alerts={[systemAlert]} />);

    expect(screen.getByText("System Status")).toBeInTheDocument();

    expect(
      screen.getByText("System service is unavailable."),
    ).toBeInTheDocument();
  });

  it("displays the Critical severity badge", () => {
    const testAlert: AlertMessage = {
      ...alert,
      severity: "critical",
    };

    render(<AlertsPanel {...defaultProps} alerts={[testAlert]} />);

    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("displays the Warning severity badge", () => {
    const testAlert: AlertMessage = {
      ...alert,
      severity: "warning",
    };

    render(<AlertsPanel {...defaultProps} alerts={[testAlert]} />);

    expect(screen.getByText("Warning")).toBeInTheDocument();
  });

  it("displays the Info severity badge", () => {
    const testAlert: AlertMessage = {
      ...alert,
      severity: "info",
    };

    render(<AlertsPanel {...defaultProps} alerts={[testAlert]} />);

    expect(screen.getByText("Info")).toBeInTheDocument();
  });

  it("defaults missing severity to Info", () => {
    const testAlert = {
      ...alert,
      severity: undefined,
    } as unknown as AlertMessage;

    render(<AlertsPanel {...defaultProps} alerts={[testAlert]} />);

    expect(screen.getByText("Info")).toBeInTheDocument();
  });

  it("sorts Critical alerts before Warning and Info", () => {
    const alerts: AlertMessage[] = [
      { ...alert, id: "info", severity: "info" },
      { ...alert, id: "warning", severity: "warning" },
      { ...alert, id: "critical", severity: "critical" },
    ];

    render(<AlertsPanel {...defaultProps} alerts={alerts} />);

    const articles = screen.getAllByRole("article");

    expect(articles[0]).toHaveTextContent("Critical");
    expect(articles[1]).toHaveTextContent("Warning");
  });

  it("filters alerts by selected severity", () => {
    const alerts: AlertMessage[] = [
      { ...alert, id: "critical", severity: "critical" },
      { ...alert, id: "warning", severity: "warning" },
      { ...alert, id: "info", severity: "info" },
    ];

    render(<AlertsPanel {...defaultProps} alerts={alerts} />);

    act(() => {
      screen.getByRole("button", { name: "warning" }).click();
    });

    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByText("warning")).toBeInTheDocument();
  });

  it("removes an alert after 5.5 seconds", () => {
    const onRemove = vi.fn();

    vi.useFakeTimers();

    try {
      render(<AlertsPanel {...defaultProps} onRemove={onRemove} />);

      expect(
        screen.getByText("Product ABC is running low."),
      ).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(5500);
      });

      expect(onRemove).toHaveBeenCalledWith("alert-1");
    } finally {
      vi.useRealTimers();
    }
  });

  it("has an accessible loading state", () => {
    render(<AlertsPanel {...defaultProps} isConnecting={true} alerts={[]} />);

    const loadingState = screen.getByRole("status");

    expect(loadingState).toBeInTheDocument();
    expect(loadingState).toHaveAttribute("aria-busy", "true");
    expect(loadingState).toHaveAttribute("aria-label", "Loading live alerts");
  });

  it("has an accessible error state", () => {
    render(<AlertsPanel {...defaultProps} failed={true} alerts={[]} />);

    const errorState = screen.getByRole("alert");

    expect(errorState).toBeInTheDocument();
    expect(errorState).toHaveTextContent(
      "Unable to connect to the alerts service.",
    );
  });

  it("has accessible individual alert", () => {
    render(<AlertsPanel {...defaultProps} />);

    const alertItem = screen.getByRole("article", {
      name: "Low Stock Item Alert: Product ABC is running low.",
    });

    expect(alertItem).toBeInTheDocument();
  });

  it("only auto-dismisses alerts that are visible", () => {
    vi.useFakeTimers();

    try {
      const onRemove = vi.fn();

      const alerts = ["a", "b", "c"].map((id) => ({
        ...alert,
        id,
      }));

      render(
        <AlertsPanel {...defaultProps} alerts={alerts} onRemove={onRemove} />,
      );

      act(() => {
        vi.advanceTimersByTime(5600);
      });

      expect(onRemove).toHaveBeenCalledWith("a");
      expect(onRemove).toHaveBeenCalledWith("b");
      expect(onRemove).not.toHaveBeenCalledWith("c");
    } finally {
      vi.useRealTimers();
    }
  });

  it("has accessible individual alert", () => {
    render(<AlertsPanel {...defaultProps} />);

    const alertItem = screen.getByRole("article", {
      name: "Low Stock Item Alert: Product ABC is running low.",
    });

    expect(alertItem).toBeInTheDocument();
  });
});
