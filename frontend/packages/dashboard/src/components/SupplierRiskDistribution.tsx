import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { supplierRisk } from "../mocks/supplierRisk";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

function SupplierRiskDistribution() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let mounted = true;

    const loadData = async () => {
      try {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, 1000);
        });

        if (mounted) {
          setError(false);
          setLoading(false);
        }
      } catch {
        if (mounted) {
          setError(true);
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      mounted = false;
    };
  }, [retryCount]);

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
  }, []);

  if (loading) {
    return (
      <div
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
        style={{
          background: colors.surface,
          borderRadius: radius.md,
          padding: space.lg,
          color: colors.danger,
        }}
      >
        <div>Failed to load supplier risk distribution.</div>

        <button
          onClick={() => {
            setError(false);
            setLoading(true);
            setRetryCount((count) => count + 1);
          }}
          style={{ marginTop: space.md }}
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
        borderRadius: radius.md,
        padding: space.lg,
      }}
    >
      <div style={{ marginBottom: space.md }}>
        <h3
          style={{
            margin: 0,
            color: colors.text,
            fontSize: "18px",
          }}
        >
          Supplier Risk Distribution
        </h3>

        <p
          style={{
            margin: `${space.xs}px 0 0`,
            color: colors.textMuted,
            fontSize: "14px",
          }}
        >
          Suppliers grouped by risk score
        </p>
      </div>

      <div style={{ width: "100%", height: 280 }}>
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
    </div>
  );
}

export default SupplierRiskDistribution;