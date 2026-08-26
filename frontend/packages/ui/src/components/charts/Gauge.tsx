import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
} from "recharts";
import "./Charts.css";

export interface GaugeProps {
  value: number;
  min?: number;
  max?: number;
  height?: number;
  label?: string;
}

export function Gauge({
  value,
  min = 0,
  max = 100,
  height = 200,
  label = "Gauge",
}: GaugeProps) {
  const clampedValue = Math.min(
    Math.max(value, min),
    max,
  );

  const range = max - min;

  const progress =
    range === 0
      ? 0
      : ((clampedValue - min) / range) * 100;

  const data = [
    {
      name: "value",
      value: progress,
    },
    {
      name: "remaining",
      value: 100 - progress,
    },
  ];

  return (
    <div
      className="gauge-container"
      style={{ height }}
      role="img"
      aria-label={`${label}: ${clampedValue}`}
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
      >
        <PieChart>
          <Pie
            data={data}
            startAngle={180}
            endAngle={0}
            cx="50%"
            cy="80%"
            innerRadius="65%"
            outerRadius="85%"
            dataKey="value"
            stroke="none"
          >
            <Cell fill="var(--color-primary)" />
            <Cell fill="var(--color-border)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>

      <div className="gauge-value">
        <strong>{clampedValue}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}