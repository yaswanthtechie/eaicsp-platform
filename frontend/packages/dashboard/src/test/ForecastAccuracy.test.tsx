import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ForecastAccuracy from "../components/ForecastAccuracy";
import { forecastAccuracy } from "../mocks/forecastAccuracy";

describe("ForecastAccuracy", () => {
  it("renders the title and description after loading", () => {
    render(
      <ForecastAccuracy
        data={forecastAccuracy}
        loading={false}
        error={false}
        onRetry={() => {}}
        startDate=""
        endDate=""
      />,
    );

    expect(screen.getByText("Forecast Accuracy")).toBeInTheDocument();

    expect(
      screen.getByText(
        "Historical forecast accuracy against the 90% target",
      ),
    ).toBeInTheDocument();
  });

  it("renders the forecast accuracy chart after loading", () => {
    render(
      <ForecastAccuracy
        data={forecastAccuracy}
        loading={false}
        error={false}
        onRetry={() => {}}
        startDate=""
        endDate=""
      />,
    );

    expect(screen.getByText("Forecast Accuracy")).toBeInTheDocument();
  });

  it("provides an accessible name for the forecast accuracy chart", () => {
    render(
      <ForecastAccuracy
        data={forecastAccuracy}
        loading={false}
        error={false}
        onRetry={() => {}}
        startDate=""
        endDate=""
      />,
    );

    expect(screen.getByText("Forecast Accuracy")).toBeInTheDocument();

    expect(
      screen.getByRole("img", {
        name: "Forecast accuracy chart showing historical accuracy and the 90 percent target",
      }),
    ).toBeInTheDocument();
  });
});
