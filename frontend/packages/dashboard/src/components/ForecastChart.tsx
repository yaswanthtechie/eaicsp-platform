import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useEffect, useState } from "react";
import { Button } from "../../../ui/src/components/Button";
import { Spinner } from "../../../ui/src/components/Spinner";
import { forecast } from "../mocks/forecast";
import { colors, radius, space } from "../tokens";

const chartData = forecast.map((item) => ({
  ...item,
  band: item.upper_bound - item.lower_bound,
}));

const lastActualIndex = chartData.reduce(
  (last, item, index) =>
    item.actual !== undefined ? index : last,
  0
);

const defaultStart =
  chartData[Math.max(0, lastActualIndex - 9)].date;

const defaultEnd =
  chartData[
    Math.min(chartData.length - 1, lastActualIndex + 5)
  ].date;

export default function ForecastChart() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

  const filteredData = chartData.filter(
    (item) => item.date >= startDate && item.date <= endDate
  );

  const resetDates = () => {
    setStartDate(chartData[0].date);
    setEndDate(chartData[chartData.length - 1].date);
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text,
        }}
      >
        <Spinner size="md" />
        <span>Loading Forecast Chart...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          color: colors.text,
          textAlign: "center",
        }}
      >
        <p>Something went wrong.</p>

        <Button
          variant="danger"
          size="sm"
          onClick={() => setError(false)}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (forecast.length === 0) {
    return (
      <div
        style={{
          color: colors.text,
          textAlign: "center",
        }}
      >
        <h2>No Forecast Data Available.</h2>
      </div>
    );
  }

  if (startDate > endDate) {
    return (
      <div
        style={{
          color: colors.text,
          textAlign: "center",
        }}
      >
        <h2 style={{ color: colors.danger }}>
          Start date must be on or before the end date.
        </h2>

        <Button
          variant="secondary"
          size="sm"
          onClick={resetDates}
        >
          Reset
        </Button>
      </div>
    );
  }

  if (filteredData.length === 0) {
    return (
      <div
        style={{
          color: colors.text,
          textAlign: "center",
        }}
      >
        <h2>No forecast data in the selected range.</h2>

        <Button
          variant="secondary"
          size="sm"
          onClick={resetDates}
        >
          Reset
        </Button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        padding: space.md,
        borderRadius: radius.md,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: space.md,
          marginBottom: space.sm,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <h2
          style={{
            color: colors.text,
            textAlign: "left",
            fontSize: space.lg,
          }}
        >
          Sales Forecasting From : {startDate} to {endDate}
        </h2>

        <label style={{ color: colors.text }}>
          Start Date:
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{
              marginLeft: space.sm,
              padding: "6px 8px",
            }}
          />
        </label>

        <label style={{ color: colors.text }}>
          End Date:
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={{
              marginLeft: space.sm,
              padding: "6px 8px",
            }}
          />
        </label>

        <Button
          variant="secondary"
          size="sm"
          onClick={resetDates}
        >
          Reset
        </Button>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={filteredData}>
          <CartesianGrid
            stroke={colors.border}
            strokeDasharray="3 4"
          />

          <XAxis
            dataKey="date"
            stroke={colors.textMuted}
          />

          <YAxis stroke={colors.textMuted} />

          <Tooltip />

          <Legend />

          <Area
            dataKey="lower_bound"
            stackId="band"
            stroke="none"
            fill="transparent"
            legendType="none"
          />

          <Area
            dataKey="band"
            stackId="band"
            stroke="none"
            fill={colors.success}
            fillOpacity={0.2}
            name="Confidence Band"
          />

          <Line
            type="monotone"
            dataKey="predicted"
            stroke={colors.primary}
            strokeWidth={5}
            dot={false}
            name="Predicted"
          />

          <Line
            type="monotone"
            dataKey="actual"
            stroke={colors.success}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={true}
            name="Actual"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}