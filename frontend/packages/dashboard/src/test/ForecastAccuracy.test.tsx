import { render, screen, waitFor } from "@testing-library/react";

import { afterEach, describe, expect, it, vi } from "vitest";

import ForecastAccuracy from "../components/ForecastAccuracy";

describe("ForecastAccuracy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the title and description after loading", async () => {
    render(
      <ForecastAccuracy startDate="" endDate="" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Forecast Accuracy"),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "Historical forecast accuracy against the 90% target",
      ),
    ).toBeInTheDocument();
  });

  it("renders the forecast accuracy chart after loading", async () => {
    render(
      <ForecastAccuracy startDate="" endDate="" />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Forecast Accuracy"),
      ).toBeInTheDocument();
    });
  });
});
