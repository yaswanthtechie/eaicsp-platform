import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { forecastAccuracy } from "../mocks/forecastAccuracy";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

function ForecastAccuracy() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      setError(false);

      try {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, 1000);
        });

        if (!cancelled) {
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      cancelled = true;
    };
  }, [retryCount]);

  if (loading) {
    return (
      <div
        style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.lg,
          padding: space.lg,
          boxSizing: "border-box",
          width: "100%",
        }}
      >
        <Skeleton width="35%" height={24} />

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="60%" height={18} />
        </div>

        <div style={{ marginTop: space.lg }}>
          <Skeleton
            width="100%"
            height={280}
            borderRadius={radius.md}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          background: colors.surface,
          border: `1px solid ${colors.danger}`,
          borderRadius: radius.lg,
          padding: space.lg,
          boxSizing: "border-box",
          width: "100%",
          minHeight: 350,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          textAlign: "center",
        }}
      >
        <h3
          style={{
            color: colors.text,
            margin: 0,
          }}
        >
          Something went wrong.
        </h3>

        <p
          style={{
            color: colors.textMuted,
            margin: 0,
          }}
        >
          Unable to load forecast accuracy data.
        </p>

        <button
          onClick={() => {
            setLoading(true);
            setRetryCount((count) => count + 1);
          }}
          style={{
            padding: "7px 14px",
            border: "none",
            borderRadius: radius.sm,
            background: colors.danger,
            color: colors.text,
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.lg,
        padding: space.lg,
        boxSizing: "border-box",
        width: "100%",
      }}
    >
      <div
        style={{
          color: colors.text,
          fontSize: 18,
          fontWeight: 600,
          marginBottom: space.xs,
        }}
      >
        Forecast Accuracy
      </div>

      <div
        style={{
          color: colors.textMuted,
          fontSize: 14,
          marginBottom: space.lg,
        }}
      >
        Historical forecast accuracy against the 90% target
      </div>

      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={forecastAccuracy}
            margin={{
              top: 8,
              right: 16,
              left: 0,
              bottom: 8,
            }}
          >
            <CartesianGrid
              stroke={colors.border}
              strokeDasharray="3 3"
            />

            <XAxis
              dataKey="date"
              tick={{ fill: colors.textMuted, fontSize: 12 }}
              tickFormatter={(date) => date.slice(5)}
            />

            <YAxis
              domain={[0, 100]}
              tick={{ fill: colors.textMuted, fontSize: 12 }}
              tickFormatter={(value) => `${value}%`}
            />

            <Tooltip
              contentStyle={{
                background: colors.surface,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.sm,
                color: colors.text,
              }}
              formatter={(value, name) => [
                `${Number(value).toFixed(2)}%`,
                name === "accuracy" ? "Accuracy" : "Target",
              ]}
            />

            <Line
              type="monotone"
              dataKey="accuracy"
              stroke={colors.primary}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />

            <Line
              type="monotone"
              dataKey="target"
              stroke={colors.success}
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ForecastAccuracy;

