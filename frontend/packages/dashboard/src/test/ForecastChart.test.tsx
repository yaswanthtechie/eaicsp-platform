import { render, screen, fireEvent, waitFor, cleanup} from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import ForecastChart from "../components/ForecastChart";
import { loadForecast } from "../mocks/forecast";

vi.mock("../mocks/forecast", () => ({
  loadForecast: vi.fn(),
}));

describe("ForecastChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(loadForecast).mockResolvedValue([
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
      screen.getByRole("button", { name: "Reset Zoom" })
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
    vi.mocked(loadForecast).mockResolvedValue([]);

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
      screen.getByRole("button", { name: "Retry" })
    ).toBeInTheDocument();
  });

  it("retries loading forecast data", async () => {
    vi.mocked(loadForecast)
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
      screen.getByRole("button", { name: "Retry" })
    );

    await waitFor(() => {
      expect(
        screen.getByText("Sales Forecast")
      ).toBeInTheDocument();
    });

    expect(loadForecast).toHaveBeenCalledTimes(2);
  });

  it("resets zoom when Reset Zoom is clicked", async () => {
    render(<ForecastChart />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Reset Zoom" })
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Reset Zoom" })
    );

    expect(
      screen.getByRole("button", { name: "Reset Zoom" })
    ).toBeInTheDocument();
  });
});

