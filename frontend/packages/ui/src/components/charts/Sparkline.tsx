import {
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";
import "./Charts.css";

export interface SparklineProps {
  data: Array<{
    value: number;
  }>;
  height?: number;
}

export function Sparkline({
  data,
  height = 60,
}: SparklineProps) {
  if (data.length === 0) {
    return (
      <div
        className="chart-empty chart-empty-small"
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
      role="img"
      aria-label="Sparkline chart"
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
      >
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--color-primary)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}