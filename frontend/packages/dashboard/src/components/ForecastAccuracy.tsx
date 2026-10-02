import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

export interface ForecastAccuracyPoint {
  date: string;
  accuracy: number;
  target: number;
}
interface ForecastAccuracyProps {
  startDate: string;
  endDate: string;
  data: ForecastAccuracyPoint[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}

function ForecastAccuracy({
  startDate,
  endDate,
  data,
  loading,
  error,
  onRetry,
}: ForecastAccuracyProps) {

  const filteredForecastAccuracy = useMemo(
    () =>
      data.filter((point) => {
        const afterStart = !startDate || point.date >= startDate;
        const beforeEnd = !endDate || point.date <= endDate;

        return afterStart && beforeEnd;
      }),
      [data, startDate, endDate],
  );

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
        aria-busy="true"
        aria-label="Loading forecast accuracy"
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
        role="alert"
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

        <Button
          type="button"
          variant="outline"
          size="lg" 
          onClick={onRetry}
        >
          Retry
        </Button>
      </div>
    );
  }


  if (filteredForecastAccuracy.length === 0) {
    return (
      <div
        role="status"
        style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.lg,
          padding: space.lg,
          boxSizing: "border-box",
          width: "100%",
          color: colors.textMuted,
        }}
      >
        No forecast accuracy data for the selected dates.
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
      <h2
        style={{
          color: colors.text,
          fontSize: 18,
          fontWeight: 600,
          marginBottom: space.xs,
        }}
      >
        Forecast Accuracy
      </h2>

      <div
        style={{
          color: colors.textMuted,
          fontSize: 14,
          marginBottom: space.lg,
        }}
      >
        Historical forecast accuracy against the 90% target
      </div>

      <div
        role="img"
        aria-label="Forecast accuracy chart showing historical accuracy and the 90 percent target"
        style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={filteredForecastAccuracy}
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
              tick={{
                fill: colors.textMuted,
                fontSize: 12,
              }}
              tickFormatter={(date) => date.slice(5)}
            />

            <YAxis
              domain={[0, 100]}
              tick={{
                fill: colors.textMuted,
                fontSize: 12,
              }}
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