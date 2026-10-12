import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

interface SupplierRiskDistributionProps {
  supplierRisk: { risk_score: number }[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}
function SupplierRiskDistribution({
  supplierRisk,
  loading,
  error,
  onRetry,
}: SupplierRiskDistributionProps) {

  const distribution = useMemo(() => {
    const result = {
      Low: 0,
      Medium: 0,
      High: 0,
    };

    supplierRisk.forEach((supplier) => {
      if (supplier.risk_score < 0.4) {
        result.Low += 1;
      } else if (supplier.risk_score < 0.7) {
        result.Medium += 1;
      } else {
        result.High += 1;
      }
    });

    return [
      { risk: "Low", count: result.Low },
      { risk: "Medium", count: result.Medium },
      { risk: "High", count: result.High },
    ];
  }, [supplierRisk]);

  if (loading) {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-label="Loading supplier risk distribution"
        style={{
          background: colors.surface,
          borderRadius: radius.md,
          padding: space.lg,
        }}
      >
        <Skeleton width="35%" height={24} />

        <div style={{ marginTop: space.md }}>
          <Skeleton width="100%" height={280} />
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
          borderRadius: radius.md,
          padding: space.lg,
          color: colors.danger,
        }}
      >
        <div>Failed to load supplier risk distribution.</div>

        <Button
          type="button"
          variant="outline"
          size="lg"
          onClick={onRetry}
          style={{ marginTop: space.md }}
        >
          Retry
        </Button>
      </div>
    );
  }

  if (supplierRisk.length === 0) {
    return (
      <div
        role="status"
        style={{
          background: colors.surface,
          borderRadius: radius.md,
          padding: space.lg,
          color: colors.textMuted,
        }}
      >
        No supplier risk data available.
      </div>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Supplier Risk Distribution</CardTitle>

        <p className="text-sm text-muted-foreground">
          Suppliers grouped by risk score
        </p>
      </CardHeader>

      <CardContent>
      <div
        role="img"
        aria-label="Supplier risk distribution chart showing suppliers grouped into low,medium and high risk" 
        style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={distribution}>
            <CartesianGrid strokeDasharray="3 3" />

            <XAxis dataKey="risk" />

            <YAxis allowDecimals={false} />

            <Tooltip />

            <Bar
              dataKey="count"
              name="Suppliers"
              fill={colors.primary}
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </CardContent>
  </Card>
  );
}

export default SupplierRiskDistribution;