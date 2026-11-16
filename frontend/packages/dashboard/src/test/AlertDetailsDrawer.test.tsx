
import { fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AlertsPanel from "../components/AlertsPanel";
import { analyticsEvents } from "../mocks/wsServer";
import type {
  AlertMessage,
  AnalyticsEventEnvelope,
} from "../types/forecast";
import { mapAnalyticsEventToAlert } from "../utils/alertMapper";

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

function renderAlert(alert: AlertMessage) {
  return render(
    <AlertsPanel
      {...defaultProps}
      alerts={[alert]}
      onRemove={vi.fn()}
    />,
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
    const alert = getMockAlert("iot.anomaly.detected");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("WH-BLR-01-S1");
    expect(dialog).toHaveTextContent("WH-BLR-01");
    expect(dialog).toHaveTextContent("Top Features");
    expect(dialog).toHaveTextContent("temperature");
    expect(dialog).toHaveTextContent("shap_value");
  });

  // 3. Supplier risk event
  it("displays supplier risk details", () => {
    const alert = getMockAlert("supplierrisk.score.changed");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("ABC Suppliers");
    expect(dialog).toHaveTextContent("SUP-00045");
    expect(dialog).toHaveTextContent("low");
    expect(dialog).toHaveTextContent("high");
    expect(dialog).toHaveTextContent("78.5");
  });

  // 4. ETA prediction event
  it("displays ETA shipment details", () => {
    const alert = getMockAlert("eta.shipment.predicted");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("SHP-2026-000077");
    expect(dialog).toHaveTextContent("PO-2026-000123");
    expect(dialog).toHaveTextContent("3.4");
    expect(dialog).toHaveTextContent("2.8");
    expect(dialog).toHaveTextContent("4.2");
  });

  // 5. Forecast batch event
  it("displays forecast batch details and nested metrics", () => {
    const alert = getMockAlert("forecast.batch.completed");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("BATCH-20261015-01");
    expect(dialog).toHaveTextContent("SUCCESS");
    expect(dialog).toHaveTextContent("prophet-xgb-r5");
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
    const alert = getMockAlert("iot.anomaly.detected");

    const { dialog } = openAlert(alert);

    expect(dialog).toHaveTextContent("Not available");
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

  it("opens the drawer when Enter is pressed on an alert", () => {
    const alert = getMockAlert("inventory.stock.low");

    renderAlert(alert);

    const alertButton = screen.getByRole("button", {
      name: /press enter to view details/i,
    });

    alertButton.focus();

    fireEvent.keyDown(alertButton, {
      key: "Enter",
      code: "Enter",
    });

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
});