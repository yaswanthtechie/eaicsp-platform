import {
  render,
  screen,
  fireEvent,
  act,
  cleanup,
} from "@testing-library/react";
import {
  describe,
  expect,
  it,
  vi,
  beforeEach,
  afterEach,
} from "vitest";
import ForecastChart from "./ForecastChart";

describe("ForecastChart", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  const finishLoading = async () => {
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
  };

  it("shows loading state", () => {
    render(<ForecastChart />);

    expect(
      screen.getByText("Loading Forecast Chart...")
    ).toBeInTheDocument();
  });

  it("shows date inputs after loading", async () => {
    render(<ForecastChart />);

    await finishLoading();

    expect(
      screen.getByLabelText("Start Date:")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("End Date:")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Reset" })
    ).toBeInTheDocument();
  });

  it("allows the start date to be changed", async () => {
    render(<ForecastChart />);

    await finishLoading();

    const startDate = screen.getByLabelText(
      "Start Date:"
    ) as HTMLInputElement;

    fireEvent.change(startDate, {
      target: {
        value: "2026-08-01",
      },
    });

    expect(startDate.value).toBe("2026-08-01");
  });

  it("allows the end date to be changed", async () => {
    render(<ForecastChart />);

    await finishLoading();

    const endDate = screen.getByLabelText(
      "End Date:"
    ) as HTMLInputElement;

    fireEvent.change(endDate, {
      target: {
        value: "2026-08-12",
      },
    });

    expect(endDate.value).toBe("2026-08-12");
  });

  it("shows an error when start date is after the end date", async () => {
    render(<ForecastChart />);

    await finishLoading();

    const startDate = screen.getByLabelText(
      "Start Date:"
    ) as HTMLInputElement;

    const endDate = screen.getByLabelText(
      "End Date:"
    ) as HTMLInputElement;

    fireEvent.change(startDate, {
      target: {
        value: "2026-08-15",
      },
    });

    fireEvent.change(endDate, {
      target: {
        value: "2026-08-10",
      },
    });

    expect(
      screen.getByText(
        "Start date must be on or before the end date."
      )
    ).toBeInTheDocument();
  });

  it("resets the selected dates", async () => {
    render(<ForecastChart />);

    await finishLoading();

    const startDate = screen.getByLabelText(
      "Start Date:"
    ) as HTMLInputElement;

    const endDate = screen.getByLabelText(
      "End Date:"
    ) as HTMLInputElement;

    fireEvent.change(startDate, {
      target: {
        value: "2026-08-01",
      },
    });

    fireEvent.change(endDate, {
      target: {
        value: "2026-08-13",
      },
    });

    expect(startDate.value).toBe("2026-08-01");
    expect(endDate.value).toBe("2026-08-13");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Reset",
      })
    );

    expect(startDate.value).toBe("2026-07-29");
    expect(endDate.value).toBe("2026-08-13");
  });
});