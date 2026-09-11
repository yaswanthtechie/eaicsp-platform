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
import { loadForecast } from "../mocks/forecast";
import { colors, radius, space } from "../tokens";
interface ForecastChartProps {
  shouldFail?: boolean;
}

export default function ForecastChart({
  shouldFail = false,
}: ForecastChartProps) {
  const [forecastData, setForecastData] = useState<
    Awaited<ReturnType<typeof loadForecast>>
  >([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      setLoading(true);
      setError(false);

      try {
        const data = await loadForecast(shouldFail);

        if (!cancelled) {
          setForecastData(data);
        }
      } catch {
        if (!cancelled) {
          setForecastData([]);
          setError(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [shouldFail, retryCount]);

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
          minHeight: 350,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text,
          textAlign: "center",
        }}
      >
        <p>Something went wrong.</p>

        <Button
          variant="danger"
          size="sm"
          onClick={() => setRetryCount((count) => count + 1)}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (forecastData.length === 0) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: colors.text,
          textAlign: "center",
        }}
      >
        <h2>No Forecast Data Available.</h2>
      </div>
    );
  }

  return <ForecastChartContent forecast={forecastData} />;
}

interface ForecastChartContentProps {
  forecast: Awaited<ReturnType<typeof loadForecast>>;
}

function ForecastChartContent({
  forecast,
}: ForecastChartContentProps) {
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

  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);

  const filteredData = chartData.filter(
    (item) =>
      item.date >= startDate &&
      item.date <= endDate
  );

  const resetDates = () => {
    setStartDate(chartData[0].date);
    setEndDate(chartData[chartData.length - 1].date);
  };

  if (startDate > endDate) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
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
          minHeight: 350,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
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
            dot
            name="Actual"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
