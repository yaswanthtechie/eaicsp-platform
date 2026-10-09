import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

interface ShipmentStatusProps {
  shipmentStatus?: {
    total: number;
    pending: number;
    delivered: number;
    in_transit: number;
    delayed: number;
    cancelled: number;
  };
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}

function ShipmentStatus({
  shipmentStatus,
  loading,
  error,
  onRetry,
}: ShipmentStatusProps) {

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
      >
        <Skeleton width="30%" height={24} />

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="55%" height={18} />
        </div>

        <div style={{ marginTop: space.lg }}>
          <Skeleton width="25%" height={18} />
        </div>

        <div style={{ marginTop: space.sm }}>
          <Skeleton
            width="100%"
            height={10}
            borderRadius={radius.sm}
          />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
            gap: space.sm,
            marginTop: space.lg,
          }}
        >
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
          <Skeleton width="100%" height={90} borderRadius={radius.md} />
        </div>

        <div style={{ marginTop: space.md }}>
          <Skeleton width="30%" height={18} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          background: colors.surface,
          border: `1px solid ${colors.danger}`,
          borderRadius: radius.lg,
          padding: space.lg,
          minHeight: 250,
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
          Failed to load shipment status.
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

  if (!shipmentStatus) {
    return (
      <div
        style={{
        color: colors.textMuted,
        padding: space.lg,
        }}
      >
        No shipment status data available.
      </div>
    );
  }
  const total = shipmentStatus.total;

  const pendingPercentage =
    total === 0 ? 0 : (shipmentStatus.pending / total) * 100;

  const inTransitPercentage =
    total === 0
      ? 0
      : (shipmentStatus.in_transit / total) * 100;

  const deliveredPercentage =
    total === 0
      ? 0
      : (shipmentStatus.delivered / total) * 100;

  const delayedPercentage =
    total === 0
      ? 0
      : (shipmentStatus.delayed / total) * 100;

  const cancelledPercentage =
    total === 0
      ? 0
      : (shipmentStatus.cancelled / total) * 100;

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Shipment Status</CardTitle>
        <p className="text-sm text-muted-foreground">
          Current shipment and logistics status
        </p>
      </CardHeader>
      <CardContent>
        <div style={{ marginBottom: space.lg }}>
          <div
            style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: space.sm,
          }}
          >
          <span
            style={{
              color: colors.textMuted,
              fontSize: 13,
            }}
          >
            Delivery progress
          </span>

          <span
            style={{
              color: colors.textMuted,
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {deliveredPercentage.toFixed(0)}%
          </span>
        </div>

        <div
          style={{
            display: "flex",
            height: 10,
            background: colors.border,
            borderRadius: radius.sm,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${pendingPercentage}%`,
              background: colors.warning,
            }}
          />

          <div
            style={{
              width: `${inTransitPercentage}%`,
              background: colors.primary,
            }}
          />

          <div
            style={{
              width: `${deliveredPercentage}%`,
              background: colors.success,
            }}
          />

          <div
            style={{
              width: `${delayedPercentage}%`,
              background: colors.danger,
            }}
          />

          <div
            style={{
              width: `${cancelledPercentage}%`,
              background: colors.textMuted,
            }}
          />
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: space.sm,
        }}
      >
        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.md,
          }}
        >
          <div style={{ color: colors.textMuted, fontSize: 12 }}>
            Pending
          </div>

          <div
            style={{
              color: colors.warning,
              fontSize: 22,
              fontWeight: 700,
              marginTop: space.xs,
            }}
          >
            {shipmentStatus.pending}
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.md,
          }}
        >
          <div style={{ color: colors.textMuted, fontSize: 12 }}>
            In Transit
          </div>

          <div
            style={{
              color: colors.primary,
              fontSize: 22,
              fontWeight: 700,
              marginTop: space.xs,
            }}
          >
            {shipmentStatus.in_transit}
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.md,
          }}
        >
          <div style={{ color: colors.textMuted, fontSize: 12 }}>
            Delivered
          </div>

          <div
            style={{
              color: colors.success,
              fontSize: 22,
              fontWeight: 700,
              marginTop: space.xs,
            }}
          >
            {shipmentStatus.delivered}
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.md,
          }}
        >
          <div style={{ color: colors.textMuted, fontSize: 12 }}>
            Delayed
          </div>

          <div
            style={{
              color: colors.danger,
              fontSize: 22,
              fontWeight: 700,
              marginTop: space.xs,
            }}
          >
            {shipmentStatus.delayed}
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.md,
          }}
        >
          <div style={{ color: colors.textMuted, fontSize: 12 }}>
            Cancelled
          </div>

          <div
            style={{
              color: colors.textMuted,
              fontSize: 22,
              fontWeight: 700,
              marginTop: space.xs,
            }}
          >
            {shipmentStatus.cancelled}
          </div>
        </div>
      </div>

      <div
        style={{
          color: colors.textMuted,
          fontSize: 13,
          marginTop: space.md,
        }}
      >
        Total shipments: {shipmentStatus.total}
      </div>
      </CardContent>
    </Card>
  );
}

export default ShipmentStatus;