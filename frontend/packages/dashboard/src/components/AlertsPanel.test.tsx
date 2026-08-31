import {cleanup, render, screen, act,} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi,} from "vitest";
import AlertsPanel from "./AlertsPanel";
import type { AlertMessage } from "../types/forecast";

describe("AlertsPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const alert: AlertMessage = {
    id: "alert-1",
    type: "low-stock",
    severity: "warning",
    message: "SKU007 stock is below threshold",
    timestamp: "2026-08-24T10:00:00.000Z",
  };

  const finishLoading = () => {
    act(() => {
      vi.advanceTimersByTime(1000);
    });
  };

  it("shows connected status", () => {
    render(
      <AlertsPanel
        alerts={[alert]}
        connected={true}
        isConnecting={false}
        failed={false}
        onRemove={vi.fn()}
      />
    );

    finishLoading();

    expect(
      screen.getByText("🟢 Connected")
    ).toBeInTheDocument();
  });

  it("shows connecting status", () => {
    render(
      <AlertsPanel
        alerts={[alert]}
        connected={false}
        isConnecting={true}
        failed={false}
        onRemove={vi.fn()}
      />
    );

    expect(
      screen.getByText("Loading Live Alerts...")
    ).toBeInTheDocument();
  });

  it("shows disconnected status", () => {
    render(
      <AlertsPanel
        alerts={[alert]}
        connected={false}
        isConnecting={false}
        failed={false}
        onRemove={vi.fn()}
      />
    );

    finishLoading();

    expect(
      screen.getByText("🔴 Disconnected")
    ).toBeInTheDocument();
  });

  it("shows no alerts message when alerts are empty", () => {
    render(
      <AlertsPanel
        alerts={[]}
        connected={true}
        isConnecting={false}
        failed={false}
        onRemove={vi.fn()}
      />
    );

    finishLoading();

    expect(
      screen.getByText("No Alerts Available.")
    ).toBeInTheDocument();
  });

  it("shows an alert", () => {
    render(
      <AlertsPanel
        alerts={[alert]}
        connected={true}
        isConnecting={false}
        failed={false}
        onRemove={vi.fn()}
      />
    );

    finishLoading();

    expect(
      screen.getByText("🟢 Connected")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Low Stock Item Alert")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/SKU007 stock is below threshold/)
    ).toBeInTheDocument();

    expect(
      screen.getByText("Warning")
    ).toBeInTheDocument();
  });

  it("removes an alert after 5.5 seconds", () => {
    const onRemove = vi.fn();

    render(
      <AlertsPanel
        alerts={[alert]}
        connected={true}
        isConnecting={false}
        failed={false}
        onRemove={onRemove}
      />
    );

    finishLoading();

    expect(
      screen.getByText("Low Stock Item Alert")
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(
      screen.getByText("Low Stock Item Alert")
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(onRemove).toHaveBeenCalledWith("alert-1");
  });
});

