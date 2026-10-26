import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsKpiPanel from "../components/AnalyticsKpiPanel";
import type { AnalyticsKpi } from "../api/kpis";

const apiMocks = vi.hoisted(() => ({
  fetchKpiDashboard: vi.fn(),
  mapKpiResponse: vi.fn(),
}));

vi.mock("../api/kpis", () => ({
  fetchKpiDashboard: apiMocks.fetchKpiDashboard,
  mapKpiResponse: apiMocks.mapKpiResponse,
}));

const kpiData: AnalyticsKpi[] = [
  {
    title: "Order Fill Rate",
    value: 94.8,
    format: "percent",
  },
  {
    title: "Inventory Stockouts",
    value: 14,
    format: "number",
  },
  {
    title: "Open Purchase Orders",
    value: 42,
    format: "number",
  },
  {
    title: "On-Time Delivery",
    value: 92.4,
    format: "percent",
  },
];

describe("AnalyticsKpiPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();

    apiMocks.fetchKpiDashboard.mockResolvedValue({});
    apiMocks.mapKpiResponse.mockReturnValue(kpiData);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the dashboard heading", async() => {
    render(<AnalyticsKpiPanel />);

    expect(
      screen.getByText("Supply Chain Performance"),
    ).toBeInTheDocument();

    // Wait for the asynchronous KPI request to finish.
    expect(
      await screen.findByText("Order Fill Rate"),
    ).toBeInTheDocument();
  });

  it("shows all four KPI cards after loading", async () => {
    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByText("Order Fill Rate"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Inventory Stockouts"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("Open Purchase Orders"),
    ).toBeInTheDocument();

    expect(
      screen.getByText("On-Time Delivery"),
    ).toBeInTheDocument();
  });

  it("formats percentage and number values correctly", async () => {
    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByRole("article", {
        name: "Order Fill Rate: 94.8%",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("article", {
        name: "Inventory Stockouts: 14",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("article", {
        name: "Open Purchase Orders: 42",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("article", {
        name: "On-Time Delivery: 92.4%",
      }),
    ).toBeInTheDocument();
  });

  it("calls the KPI API when the component loads", async () => {
    render(<AnalyticsKpiPanel />);

    await waitFor(() => {
      expect(apiMocks.fetchKpiDashboard).toHaveBeenCalledTimes(1);
    });

    expect(apiMocks.mapKpiResponse).toHaveBeenCalledWith({});

    expect(
      await screen.findByText("Order Fill Rate"),
    ).toBeInTheDocument();
  });

  it("shows the empty state when no KPI data is returned", async () => {
    apiMocks.mapKpiResponse.mockReturnValue([]);

    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByText("No analytics KPI data available."),
    ).toBeInTheDocument();
  });

  it("shows an accessible error when the API request fails", async () => {
    apiMocks.fetchKpiDashboard.mockRejectedValue(
      new Error("KPI service unavailable"),
    );

    render(<AnalyticsKpiPanel />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    expect(
      screen.getByText("KPI service unavailable"),
    ).toBeInTheDocument();
  });

  it("retries the API request when Retry is clicked", async () => {
    apiMocks.fetchKpiDashboard
      .mockRejectedValueOnce(new Error("Temporary failure"))
      .mockResolvedValueOnce({});

    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByText("Temporary failure"),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Retry" }),
    );

    await waitFor(() => {
      expect(apiMocks.fetchKpiDashboard).toHaveBeenCalledTimes(2);
    });

    expect(
      await screen.findByText("Order Fill Rate"),
    ).toBeInTheDocument();
  });

  it("refreshes KPI data when the Refresh button is clicked", async () => {
    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByText("Order Fill Rate"),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Refresh analytics KPIs",
      }),
    );

    await waitFor(() => {
      expect(apiMocks.fetchKpiDashboard).toHaveBeenCalledTimes(2);
    });
  });

  it("shows previously saved KPI values when the API fails", async () => {
    localStorage.setItem(
      "analytics-kpi-snapshot:v1",
      JSON.stringify(kpiData),
    );

    apiMocks.fetchKpiDashboard.mockRejectedValue(
      new Error("Service unavailable"),
    );

    render(<AnalyticsKpiPanel />);

    expect(
      await screen.findByText(
        "KPI service unavailable. Showing the last saved values.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getAllByText("Last saved value"),
    ).toHaveLength(4);

    expect(
      screen.getByText("Order Fill Rate"),
    ).toBeInTheDocument();
  });

  it("handles invalid saved snapshot data without crashing", async () => {
    localStorage.setItem(
      "analytics-kpi-snapshot:v1",
      JSON.stringify([{ invalid: true }]),
    );

    apiMocks.fetchKpiDashboard.mockRejectedValue(
      new Error("KPI service unavailable"),
    );

    render(<AnalyticsKpiPanel />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    expect(
      screen.getByText("KPI service unavailable"),
    ).toBeInTheDocument();
  });
});
