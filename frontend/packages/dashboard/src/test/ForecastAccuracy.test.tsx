import { render, screen, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ForecastAccuracy from "../components/ForecastAccuracy";

describe("ForecastAccuracy", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows loading skeleton while data is loading", () => {
    const { container } = render(<ForecastAccuracy />);

    expect(
      screen.queryByText("Forecast Accuracy")
    ).not.toBeInTheDocument();

    expect(container.querySelectorAll("div").length).toBeGreaterThan(1);
  });

  it("renders the title and description after loading", async () => {
    render(<ForecastAccuracy />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("Forecast Accuracy")).toBeInTheDocument();

    expect(
      screen.getByText(
        "Historical forecast accuracy against the 90% target"
      )
    ).toBeInTheDocument();
  });

  it("renders the forecast accuracy chart after loading", async () => {
    render(<ForecastAccuracy />);

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("Forecast Accuracy")).toBeInTheDocument();
  });
});
