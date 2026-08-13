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
import { forecast } from "../mocks/forecast";
import { colors } from "../tokens";

const chartData = forecast.map((item) => ({
  ...item,
  band: item.upper_bound - item.lower_bound,
}));

// "Today" is the last date we have an actual for;
// everything after is forecast.
const lastActualIndex = chartData.reduce(
  (last, item, index) =>
    item.actual !== undefined ? index : last,
  0
);

// Spec default: last 10 days + next 5 days.
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
      <h2 style={{ color: colors.text }}>
        Loading Sales Forecast Data....
      </h2>
    );
  }

  if (error) {
    return (
      <div style={{ color: colors.text }}>
        <p>Something went wrong.</p>

        <button onClick={() => setError(false)}>
          Retry
        </button>
      </div>
    );
  }

  if (forecast.length === 0) {
    return (
      <h2 style={{ color: colors.text }}>
        No Forecast Data Available.
      </h2>
    );
  }

  if (startDate > endDate) {
    return (
      <div style={{ color: colors.text }}>
        <h2 style={{ color: colors.danger }}>
          Start date must be on or before the end date.
        </h2>

        <button
          onClick={resetDates}
          style={{
            padding: "7px 14px",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
      </div>
    );
  }

  if (filteredData.length === 0) {
    return (
      <div style={{ color: colors.text }}>
        <h2>No forecast data in the selected range.</h2>

        <button
          onClick={resetDates}
          style={{
            padding: "7px 14px",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        padding: 20,
        borderRadius: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 16,
          marginBottom: 20,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <label style={{ color: colors.text }}>
          Start Date:
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{
              marginLeft: 8,
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
              marginLeft: 8,
              padding: "6px 8px",
            }}
          />
        </label>

        <button
          onClick={resetDates}
          style={{
            padding: "7px 14px",
            cursor: "pointer",
          }}
        >
          Reset
        </button>
      </div>

      <h2
        style={{
          color: colors.text,
          textAlign: "center",
        }}
      >
        Sales Forecasting From : {startDate} to {endDate}
      </h2>

      <ResponsiveContainer width="100%" height={400}>
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