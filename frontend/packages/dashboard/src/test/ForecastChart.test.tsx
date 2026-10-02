import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ForecastChart from "../components/ForecastChart";

const forecastData = [
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
];

describe("ForecastChart", () => {
  const defaultProps = {
    data: forecastData,
    loading: false,
    error: false,
    onRetry: vi.fn(),
  };

  it("shows loading skeleton while forecast data is loading", () => {
    render(
      <ForecastChart
        {...defaultProps}
        loading={true}
      />,
    );

    expect(
      screen.getByLabelText("Loading sales forecast"),
    ).toHaveAttribute("aria-busy", "true");
  });

  it("shows forecast chart", () => {
    render(<ForecastChart {...defaultProps} />);

    expect(
      screen.getByText("Sales Forecast"),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Reset sales forecast zoom",
      }),
    ).toBeInTheDocument();
  });

  it("shows selected date range", () => {
    render(
      <ForecastChart
        {...defaultProps}
        startDate="2026-08-04"
        endDate="2026-08-10"
      />,
    );

    expect(
      screen.getByText("2026-08-04 → 2026-08-10"),
    ).toBeInTheDocument();
  });

  it("shows no data message when forecast data is empty", () => {
    render(
      <ForecastChart
        {...defaultProps}
        data={[]}
      />,
    );

    expect(
      screen.getByText("No forecast data available."),
    ).toBeInTheDocument();
  });

  it("shows no data message when selected date range has no data", () => {
    render(
      <ForecastChart
        {...defaultProps}
        startDate="2026-09-01"
        endDate="2026-09-10"
      />,
    );

    expect(
      screen.getByText(
        "No forecast data for the selected date range.",
      ),
    ).toBeInTheDocument();
  });

  it("calls retry when Retry is clicked", () => {
    const onRetry = vi.fn();

    render(
      <ForecastChart
        {...defaultProps}
        error={true}
        onRetry={onRetry}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Retry loading sales forecast",
      }),
    );

    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows accessible error state", () => {
    render(
      <ForecastChart
        {...defaultProps}
        error={true}
      />,
    );

    expect(
      screen.getByRole("alert"),
    ).toBeInTheDocument();
  });

  it("provides an accessible name for the forecast chart", () => {
    render(<ForecastChart {...defaultProps} />);

    expect(
      screen.getByRole("img", {
        name:
          "Sales forecast chart showing predicted and actual values with a confidence band",
      }),
    ).toBeInTheDocument();
  });

  it("resets zoom when Reset Zoom is activated", () => {
    render(<ForecastChart {...defaultProps} />);

    const resetButton = screen.getByRole("button", {
      name: "Reset sales forecast zoom",
    });

    fireEvent.click(resetButton);

    expect(resetButton).toBeInTheDocument();
  });
});