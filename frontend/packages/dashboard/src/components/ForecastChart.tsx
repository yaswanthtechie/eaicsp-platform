import {
    Area,
    Brush,
    CartesianGrid,
    ComposedChart,
    Legend,
    Line,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import { useEffect, useMemo, useState } from "react";
import { loadForecast } from "../mocks/forecast";
import { colors, space } from "../tokens";
import type { ForecastPoint } from "../types/forecast";
import Skeleton from "./Skeleton";
interface ForecastChartProps {
  startDate?: string;
  endDate?: string;
  shouldFail?: boolean;
}

function ForecastChart({
  startDate = "",
  endDate = "",
  shouldFail = false,
}: ForecastChartProps) {
  const [forecastData, setForecastData] = useState<ForecastPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [zoomStart, setZoomStart] = useState<number | null>(null);
  const [zoomEnd, setZoomEnd] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(false);

    try {
      if (shouldFail) {
        throw new Error("Failed to load forecast data");
      }

      const data = await loadForecast();
      setForecastData(data);
    } catch {
      setForecastData([]);
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError(false);

      try {
        if (shouldFail) {
          throw new Error("Failed to load forecast data");
        }

        const data = await loadForecast();

        if (!cancelled) {
          setForecastData(data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setForecastData([]);
          setError(true);
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      cancelled = true;
    };
  }, [shouldFail]);

  const filteredData = useMemo(() => {
    return forecastData.filter((item) => {
      const matchesStart =
        !startDate || item.date >= startDate;

      const matchesEnd =
        !endDate || item.date <= endDate;

      return matchesStart && matchesEnd;
    });
  }, [forecastData, startDate, endDate]);

  const chartData = useMemo(() => {
    return filteredData.map((item) => ({
      ...item,
      band: item.upper_bound - item.lower_bound,
    }));
  }, [filteredData]);

  const handleResetZoom = () => {
    setZoomStart(null);
    setZoomEnd(null);
  };

  const handleZoomChange = (range: {
    startIndex?: number;
    endIndex?: number;
  }) => {
    if (
      range.startIndex !== undefined &&
      range.endIndex !== undefined
    ) {
      setZoomStart(range.startIndex);
      setZoomEnd(range.endIndex);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          padding: space.lg,
        }}
      >
        <Skeleton width="35%" height={28} />
        <div style={{ marginTop: space.sm }}>
          <Skeleton width="20%" height={16} />
        </div>
        <div style={{ marginTop: space.md }}>
          <Skeleton
            width="100%"
            height={400}
            borderRadius={10}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          color: colors.danger,
          padding: space.lg,
        }}
      >
        <p>Something went wrong.</p>

        <button onClick={fetchData}>
          Retry
        </Button>
      </div>
    );
  }

  if (forecastData.length === 0) {
    return (
      <div
        style={{
          color: colors.textMuted,
          padding: space.lg,
        }}
      >
        No forecast data available.
      </div>
    );
  }

  if (filteredData.length === 0) {
    return (
      <div
        style={{
          color: colors.textMuted,
          padding: space.lg,
        }}
      >
        No forecast data for the selected date range.
      </div>
    );
  }

  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: space.md,
        }}
      >
        <div>
          <h2
            style={{
              color: colors.text,
              marginTop: 0,
              marginBottom: space.sm,
            }}
          >
            Sales Forecast
          </h2>

          <div
            style={{
              color: colors.textMuted,
              fontSize: 14,
            }}
          >
            {startDate || "Start"} → {endDate || "End"}
          </div>
        </div>

        <button
          onClick={handleResetZoom}
          style={{
            padding: "8px 12px",
            borderRadius: 6,
            border: `1px solid ${colors.border}`,
            background: colors.surface,
            color: colors.text,
            cursor: "pointer",
          }}
        >
          Reset Zoom
        </button>
      </div>

      <div
        style={{
          width: "100%",
          height: 400,
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData}>
            <CartesianGrid stroke={colors.border} />

            <XAxis
              dataKey="date"
              stroke={colors.textMuted}
            />

            <YAxis stroke={colors.textMuted} />

            <Tooltip />

            <Legend />

            <Area
              type="monotone"
              dataKey="lower_bound"
              stackId="confidence"
              stroke="none"
              fill="transparent"
            />

            <Area
              type="monotone"
              dataKey="band"
              stackId="confidence"
              stroke="none"
              fill={colors.primary}
              fillOpacity={0.15}
            />

            <Line
              type="monotone"
              dataKey="predicted"
              stroke={colors.primary}
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="actual"
              stroke={colors.success}
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
            />

            <Brush
              dataKey="date"
              height={30}
              stroke={colors.primary}
              startIndex={zoomStart ?? 0}
              endIndex={
                zoomEnd ?? chartData.length - 1
              }
              onChange={handleZoomChange}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ForecastChart;

