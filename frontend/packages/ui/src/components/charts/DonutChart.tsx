import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import "./Charts.css";

export interface DonutChartProps {
  data: Array<{
    name: string;
    value: number;
  }>;
  height?: number;
}

export const DonutChart: React.FC<DonutChartProps> = ({
  data,
  height = 300,
}) => {
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius="55%"
            outerRadius="75%"
            paddingAngle={2}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${entry.name}-${index}`} />
            ))}
          </Pie>

          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};