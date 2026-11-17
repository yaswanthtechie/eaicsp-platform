import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import AlertsPanel from "../components/AlertsPanel";
import { analyticsEvents } from "../mocks/wsServer";
import type { AlertMessage, AnalyticsEventEnvelope } from "../types/forecast";
import { mapAnalyticsEventToAlert } from "../utils/alertMapper";
import { alertEventFixtures } from "./fixtures/alertEventFixtures";

vi.mock("../components/Skeleton", () => ({
  default: ({ width, height }: { width: string; height: number }) => (
    <div data-testid="skeleton">
      {width}-{height}
    </div>
  ),
}));

const defaultProps = {
  connected: true,
  isConnecting: false,
  failed: false,
  onRemove: vi.fn(),
};

function getMockAlert(eventType: string): AlertMessage {
  const mockEvent = analyticsEvents.find(
    (event) => event.event_type === eventType,
  );

  if (!mockEvent) {
    throw new Error(`Mock event not found: ${eventType}`);
  }

  const envelope: AnalyticsEventEnvelope = {
    event_id: `test-${eventType}`,
    occurred_at: "2026-11-16T10:30:00.000Z",
    ...mockEvent,
  };

  const mappedAlert = mapAnalyticsEventToAlert(envelope);

  if (!mappedAlert) {
    throw new Error(`Could not map event: ${eventType}`);
  }

  return mappedAlert;
}

function getContractAlert(
  event: AnalyticsEventEnvelope,
): AlertMessage {
  const mappedAlert = mapAnalyticsEventToAlert(event);

  if (!mappedAlert) {
    throw new Error(`Could not map event: ${event.event_type}`);
  }

  return mappedAlert;
}

function renderAlert(alert: AlertMessage) {
  return render(
    <AlertsPanel {...defaultProps} alerts={[alert]} onRemove={vi.fn()} />,
  );
}

function openAlert(alert: AlertMessage) {
  renderAlert(alert);

  const alertButton = screen.getByRole("button", {
    name: /press enter to view details/i,
  });

  fireEvent.click(alertButton);

  const dialog = screen.getByRole("dialog");

  return { alertButton, dialog };
}

describe("C6 - Alert Details Drawer", () => {
  // 1. Inventory stock event
  it("displays inventory stock details", () => {
    const alert = getMockAlert("inventory.stock.low");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("Alert Details");
    expect(dialog).toHaveTextContent("SKU-000123");
    expect(dialog).toHaveTextContent("WH-BLR-01");
    expect(dialog).toHaveTextContent("35");
    expect(dialog).toHaveTextContent("15");
  });

  // 2. IoT anomaly event
  it("displays IoT anomaly details and top features", () => {
    const alert = getContractAlert(alertEventFixtures.iot);

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("WH-BLR-01-S1");
    expect(dialog).toHaveTextContent("WH-BLR-01");
    expect(dialog).toHaveTextContent("Top Features");
    expect(dialog).toHaveTextContent("temperature");
    expect(dialog).toHaveTextContent("shap_value");
  });

  // 3. Supplier risk event
  it("displays supplier risk details", () => {
    const alert = getContractAlert(alertEventFixtures.supplierrisk);

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("Unity Manufacturing GmbH");
    expect(dialog).toHaveTextContent("SUP-00019");
    expect(dialog).toHaveTextContent("medium");
    expect(dialog).toHaveTextContent("high");
    expect(dialog).toHaveTextContent("78.5");
  });

  // 4. ETA prediction event
  it("displays ETA shipment details", () => {
    const alert = getContractAlert(alertEventFixtures.eta);

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("SHP-2026-000077");
    expect(dialog).toHaveTextContent("PO-2026-000123");
    expect(dialog).toHaveTextContent("5.2");
    expect(dialog).toHaveTextContent("4.1");
    expect(dialog).toHaveTextContent("7.3");
  });

  // 5. Forecast batch event
  it("displays forecast batch details and nested metrics", () => {
    const alert = getContractAlert(alertEventFixtures.forecastBatch);

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("BATCH-20261015-01");
    expect(dialog).toHaveTextContent("SUCCESS");
    expect(dialog).toHaveTextContent("demand_forecast/4");
    expect(dialog).toHaveTextContent("0.118");
    expect(dialog).toHaveTextContent("0.094");
    expect(dialog).toHaveTextContent("24.5");
  });

  // 6. Data pipeline event
  it("displays data pipeline details and nested task states", () => {
    const alert = getMockAlert("data.pipeline.completed");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("1042");
    expect(dialog).toHaveTextContent("SUCCESS");
    expect(dialog).toHaveTextContent("12450");
    expect(dialog).toHaveTextContent("320");
    expect(dialog).toHaveTextContent("sales_etl_pipeline");
    expect(dialog).toHaveTextContent("dbt_build");
    expect(dialog).toHaveTextContent("clickhouse_load");
  });

  it("displays raw payload for an unknown event type", () => {
    const unknownAlert: AlertMessage = {
      id: "test-unknown-001",
      type: "system",
      severity: "info",
      title: "Unknown Test Event",
      message: "Synthetic unknown event",
      timestamp: "2026-11-16T10:30:00.000Z",
      eventType: "test.unknown.event",
      producer: "test-service",
      eventVersion: "1.0",
      payload: {
        test_field: "Test value",
        test_count: 10,
        test_status: "completed",
      },
    };

    const { dialog } = openAlert(unknownAlert);

    expect(dialog).toHaveTextContent("test.unknown.event");
    expect(dialog).toHaveTextContent("Test Field");
    expect(dialog).toHaveTextContent("Test value");
    expect(dialog).toHaveTextContent("Test Count");
    expect(dialog).toHaveTextContent("10");
    expect(dialog).toHaveTextContent("Test Status");
    expect(dialog).toHaveTextContent("completed");
  });

  it("displays Not available when an optional payload field is missing", () => {
    const base = getContractAlert(alertEventFixtures.eta);
    const payload = { ...base.payload };
    delete payload.top_features;

    const { dialog } = openAlert({ ...base, traceId: "trace-1", payload });

    const row = within(dialog).getByText("Top Features").parentElement;
    expect(row).toHaveTextContent("Not available");
    expect(dialog).not.toHaveTextContent("undefined");
  });

  it("opens the drawer when an alert is clicked", () => {
    const alert = getMockAlert("inventory.stock.low");

    renderAlert(alert);

    const alertButton = screen.getByRole("button", {
      name: /press enter to view details/i,
    });

    fireEvent.click(alertButton);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("opens the drawer when Enter is pressed on an alert", async() => {
    const user = userEvent.setup();
    const alert = getMockAlert("inventory.stock.low");

    renderAlert(alert);

    const alertButton = screen.getByRole("button", {
      name: /press enter to view details/i,
    });

    alertButton.focus();

    await user.keyboard("{Enter}");

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes the drawer when Escape is pressed", async () => {
    const alert = getMockAlert("inventory.stock.low");

    const { dialog } = openAlert(alert);

    fireEvent.keyDown(dialog, {
      key: "Escape",
      code: "Escape",
    });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("closes the drawer using the close button", async () => {
    const alert = getMockAlert("inventory.stock.low");

    openAlert(alert);

    const closeButton = screen.getByRole("button", {
      name: /close alert details/i,
    });

    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("returns focus to the alert after the drawer closes", async () => {
    const alert = getMockAlert("inventory.stock.low");

    const { alertButton, dialog } = openAlert(alert);

    fireEvent.keyDown(dialog, {
      key: "Escape",
      code: "Escape",
    });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(alertButton).toHaveFocus();
    });
  });

  it("keeps the opened alert and its drawer while the drawer is open", () => {
    vi.useFakeTimers();

    try {
      const base = getMockAlert("inventory.stock.low");

      function Harness() {
        const [alerts, setAlerts] = useState<AlertMessage[]>([base]);

        return (
          <AlertsPanel
            {...defaultProps}
            alerts={alerts}
            onRemove={(id) =>
              setAlerts((prev) => prev.filter((a) => a.id !== id))
            }
          />
        );
      }

      render(<Harness />);

      const alertButton = screen.getByRole("button", {
        name: /press enter to view details/i,
      });

      act(() => {
        vi.advanceTimersByTime(3000);
      });

      fireEvent.click(alertButton);

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(alertButton).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows the raw payload of an unknown event type that came through the mapper", () => {
    const alert = mapAnalyticsEventToAlert({
      event_id: "test-sales-anomaly",
      event_type: "sales.anomaly.detected",
      event_version: 1,
      occurred_at: "2026-11-16T10:30:00.000Z",
      producer: "anomaly-detection",
      severity: "warning",
      payload: {
        sku_id: "SKU-000501",
        warehouse_id: "WH-BLR-01",
        expected: 50,
      },
    });

    expect(alert).not.toBeNull();

    const { dialog } = openAlert(alert as AlertMessage);

    expect(dialog).toHaveTextContent("sales.anomaly.detected");
    expect(dialog).toHaveTextContent("SKU-000501");
    expect(dialog).toHaveTextContent("WH-BLR-01");
  });

  it("shows Not available for an invalid timestamp", () => {
    const base = getMockAlert("inventory.stock.low");

    const { dialog } = openAlert({ ...base, timestamp: "not-a-date" });

    expect(dialog).not.toHaveTextContent("Invalid Date");
  });
});
