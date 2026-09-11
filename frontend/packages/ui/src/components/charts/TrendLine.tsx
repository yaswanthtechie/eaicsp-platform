import "./Charts.css";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TrendLineProps<T extends object> {
  data: T[];
  xKey: keyof T;
  yKey: keyof T;
  height?: number;
}

export function TrendLine<T extends object>({
  data,
  xKey,
  yKey,
  height = 250,
}: TrendLineProps<T>) {
  if (data.length === 0) {
    return (
      <div
        className="chart-empty"
        role="status"
        aria-live="polite"
      >
        No data available
      </div>
    );
  }

  return (
    <div
      className="chart-container"
      style={{ height }}
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
      >
        <LineChart data={data}>
          <CartesianGrid
            stroke="currentColor"
            strokeOpacity={0.15}
          />

          <XAxis
            dataKey={String(xKey)}
            stroke="currentColor"
          />

          <YAxis stroke="currentColor" />

          <Tooltip />

          <Line
            type="monotone"
            dataKey={String(yKey)}
            stroke="currentColor"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}