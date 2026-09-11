import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export interface MiniBarChartProps<T extends Record<string, unknown>> {
  data: T[];
  xKey: keyof T;
  yKey: keyof T;
  height?: number;
}

export function MiniBarChart<T extends Record<string, unknown>>({
  data,
  xKey,
  yKey,
  height = 200,
}: MiniBarChartProps<T>) {
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey={String(xKey)} />
          <YAxis />
          <Tooltip />
          <Bar dataKey={String(yKey)} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}