import { Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { colors, radius, space } from "../tokens";
import type { SupplierRiskItem } from "../types/dashboard";
import Skeleton from "./Skeleton";

interface SupplierRiskProps {
  supplierRisk: SupplierRiskItem[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}

function SupplierRisk({
  supplierRisk,
  loading,
  error,
  onRetry,
}: SupplierRiskProps) {


  if (loading) {
    return (
      <div
        style={{
          background: colors.surface,
          borderRadius: radius.lg,
          padding: space.lg,
        }}
      >
        <Skeleton width="30%" height={24} />

        <div style={{ marginTop: space.md }}>
          <Skeleton width="100%" height={250} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          background: colors.surface,
          borderRadius: radius.lg,
          padding: space.lg,
          color: colors.danger,
        }}
      >
        <div>Failed to load supplier risk.</div>

        <Button
          type="button"
          variant="outline"
          onClick={onRetry}
          style={{ marginTop: space.md }}
        >
          Retry
        </Button>
      </div>
    );
  }

  const getRiskColor = (riskScore: number) => {
    if (riskScore >= 0.7) {
      return colors.danger;
    }

    if (riskScore >= 0.4) {
      return colors.warning;
    }

    return colors.success;
  };

  const getRiskLevel = (riskScore: number) => {
    if (riskScore >= 0.7) {
      return "High";
    }

    if (riskScore >= 0.4) {
      return "Medium";
    }

    return "Low";
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Supplier Risk Summary</CardTitle>

        <p className="text-sm text-muted-foreground">
          Risk score and model confidence by supplier
        </p>
      </CardHeader>

      <CardContent>
        <div
          style={{
            display: "grid",
            gap: space.sm,
          }}
        >
          {supplierRisk.map((supplier) => {
            const riskColor = getRiskColor(supplier.risk_score);
            const riskLevel = getRiskLevel(supplier.risk_score);

            return (
              <div
                key={supplier.supplier}
                style={{
                  border: `1px solid ${colors.border}`,
                  borderRadius: radius.md,
                  padding: space.md,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: space.md,
                  }}
                >
                  <div
                    style={{
                      color: colors.textMuted,
                      fontWeight: 700,
                    }}
                  >
                    {supplier.supplier}
                  </div>

                  <div
                    style={{
                      color: riskColor,
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    {riskLevel} Risk
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: space.md,
                  }}
                >
                  <div>
                    <div
                      style={{
                        color: colors.textMuted,
                        fontSize: 12,
                      }}
                    >
                      Risk Score
                    </div>

                    <div
                      style={{
                        color: riskColor,
                        fontWeight: 600,
                        marginTop: space.xs,
                      }}
                    >
                      {(supplier.risk_score * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div>
                    <div
                      style={{
                        color: colors.textMuted,
                        fontSize: 12,
                      }}
                    >
                      Confidence
                    </div>

                    <div
                      style={{
                        color: colors.textMuted,
                        fontWeight: 700,
                        marginTop: space.xs,
                      }}
                    >
                      {(supplier.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: space.md }}>
                  <div
                    style={{
                      color: colors.textMuted,
                      fontSize: 12,
                      marginBottom: space.xs,
                    }}
                  >
                    Sentiment
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: space.md,
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: colors.success }}>
                      Positive{" "}
                      {(supplier.sentiment_breakdown.positive * 100).toFixed(
                        0,
                      )}
                      %
                    </span>

                    <span style={{ color: colors.danger }}>
                      Negative{" "}
                      {(supplier.sentiment_breakdown.negative * 100).toFixed(
                        0,
                      )}
                      %
                    </span>

                    <span style={{ color: colors.textMuted }}>
                      Neutral{" "}
                      {(supplier.sentiment_breakdown.neutral * 100).toFixed(0)}
                      %
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export default SupplierRisk;