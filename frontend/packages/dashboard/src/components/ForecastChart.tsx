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

export default function ForecastChart() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(()=>{
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);
    return () =>clearTimeout(timer);
  },[]);

  if(loading){
    return <h2>Loading Sales Forecast Data....</h2>
  }
  if(error){
    return(
      <div>
        <h2>Something went wrong.</h2>
        <button onClick={() => setError(false)}>Retry</button>
      </div>
    );
  }
  if(forecast.length == 0){
    return <h2>No Forecast Data Available.</h2>;
  }
  return (
    <div
      style={{
        background: colors.surface,
        padding: 20,
        borderRadius: 10,
      }}
    >
      <h2 style={{ color: colors.text ,textAlign:"center"}}>Sales Forecasting</h2>

      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData}>
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