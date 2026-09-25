import { render, screen, fireEvent, waitFor, cleanup} from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import ForecastChart from "../components/ForecastChart";
import { dashboardApi } from "../api/dashboard";

vi.mock("../api/dashboard", () => ({
  dashboardApi: {
    fetchForecast:vi.fn(),
  },
}));

describe("ForecastChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(dashboardApi.fetchForecast).mockResolvedValue([
      {
        date: "2026-08-01",
        predicted: 100,
        actual: 95,
        lower_bound: 80,
        upper_bound: 120,
      },
      {
        date: "2026-08-05",
        predicted: 110,
        actual: 105,
        lower_bound: 90,
        upper_bound: 130,
      },
      {
        date: "2026-08-10",
        predicted: 120,
        actual: 115,
        lower_bound: 100,
        upper_bound: 140,
      },
    ]);
  });

  afterEach(() => {
    cleanup();
  });

  it("shows loading skeleton while forecast data is loading", () => {
    const { container } = render(<ForecastChart />);

    expect(
      screen.queryByText("Sales Forecast")
    ).not.toBeInTheDocument();

    expect(container.querySelectorAll("div").length).toBeGreaterThan(1);
  });

  it("shows forecast chart after loading", async () => {
    render(<ForecastChart />);

    await waitFor(() => {
      expect(
        screen.getByText("Sales Forecast")
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: "Reset sales forecast zoom" })
    ).toBeInTheDocument();
  });

  it("shows selected date range", async () => {
    render(
      <ForecastChart
        startDate="2026-08-04"
        endDate="2026-08-10"
      />
    );

    expect(
      await screen.findByText("2026-08-04 → 2026-08-10")
    ).toBeInTheDocument();
  });

  it("shows no data message when forecast data is empty", async () => {
    vi.mocked(dashboardApi.fetchForecast).mockResolvedValue([]);

    render(<ForecastChart />);

    expect(
      await screen.findByText("No forecast data available.")
    ).toBeInTheDocument();
  });

  it("shows no data message when selected date range has no data", async () => {
    render(
      <ForecastChart
        startDate="2026-09-01"
        endDate="2026-09-10"
      />
    );

    expect(
      await screen.findByText(
        "No forecast data for the selected date range."
      )
    ).toBeInTheDocument();
  });

  it("shows error state when shouldFail is true", async () => {
    render(<ForecastChart shouldFail />);

    expect(
      await screen.findByText("Something went wrong.")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Retry loading sales forecast" })
    ).toBeInTheDocument();
  });

  it("retries loading forecast data", async () => {
    vi.mocked(dashboardApi.fetchForecast)
      .mockRejectedValueOnce(new Error("Failed"))
      .mockResolvedValueOnce([
        {
          date: "2026-08-01",
          predicted: 100,
          actual: 95,
          lower_bound: 80,
          upper_bound: 120,
        },
      ]);

    render(<ForecastChart />);

    expect(
      await screen.findByText("Something went wrong.")
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Retry loading sales forecast" })
    );

    await waitFor(() => {
      expect(
        screen.getByText("Sales Forecast")
      ).toBeInTheDocument();
    });

    expect(dashboardApi.fetchForecast).toHaveBeenCalledTimes(2);
  });

  it("resets zoom when Reset Zoom is activated with Enter", async () => {
    render(<ForecastChart />);

    const resetButton = await screen.findByRole("button", {
      name: "Reset sales forecast zoom",
    });

    resetButton.focus();

    fireEvent.keyDown(resetButton, {
      key: "Enter",
      code: "Enter",
    });

    fireEvent.keyUp(resetButton, {
      key: "Enter",
      code: "Enter",
    });

    expect(resetButton).toBeInTheDocument();
});

  it("shows accessible loading state", () => {
    const { container } = render(<ForecastChart />);

    const loadingContainer = container.querySelector(
      '[aria-label="Loading sales forecast"]'
    );

    expect(loadingContainer).toHaveAttribute("aria-busy","true");
  });

  it("shows accessible error state", async () => {
    render(<ForecastChart shouldFail />);

    const errorContainer = await screen.findByRole("alert");

    expect(errorContainer).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Retry loading sales forecast",
      })
    ).toBeInTheDocument();
  });

  it("provides an accessible name for the forecast chart", async () => {
    render(<ForecastChart />);

    await screen.findByText("Sales Forecast");

    expect(
      screen.getByRole("img", {
        name: "Sales forecast chart showing predicted and actual values with a confidence band",
      })
    ).toBeInTheDocument();
  });
});

