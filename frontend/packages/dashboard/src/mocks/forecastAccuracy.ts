import type { ForecastAccuracyPoint } from "../types/dashboard.ts";
import { forecast } from "./forecast.ts";

export const forecastAccuracy: ForecastAccuracyPoint[] = forecast
  .filter((point) => point.actual !== undefined)
  .map((point) => {
    const actual = point.actual as number;

    const accuracy =
      actual === 0
        ? 0
        : Math.max(
            0,
            100 -
              (Math.abs(actual - point.predicted) / actual) * 100,
          );

    return {
      date: point.date,
      accuracy: Number(accuracy.toFixed(2)),
      target: 90,
    };
  });