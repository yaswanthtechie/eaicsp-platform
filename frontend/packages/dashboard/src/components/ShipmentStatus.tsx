import { useEffect, useState } from "react";
import { shipmentStatus } from "../mocks/shipments";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

function ShipmentStatus() {
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
            gridTemplateColumns:
              "repeat(5, minmax(0, 1fr))",
            gap: space.sm,
            marginTop: space.lg,
          }}
        >
          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={90}
            borderRadius={radius.md}
          />
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

        <button
          type="button"
          onClick={() => {
            setError(false);
            setLoading(true);
            setRetryCount((count) => count + 1);
          }}
          style={{
            padding: "7px 14px",
            border: "none",
            borderRadius: radius.sm,
            background: colors.danger,
            color: colors.text,
            cursor: "pointer",
          }}
        >
          Retry
        </button>
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
      <div
        style={{
          color: colors.text,
          fontSize: 18,
          fontWeight: 600,
          marginBottom: space.xs,
        }}
      >
        Shipment Status
      </div>

      <div
        style={{
          color: colors.textMuted,
          fontSize: 14,
          marginBottom: space.lg,
        }}
      >
        Current shipment and logistics status
      </div>

      <div
        style={{
          marginBottom: space.lg,
        }}
      >
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
              color: colors.text,
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
          <div
            style={{
              color: colors.textMuted,
              fontSize: 12,
            }}
          >
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
          <div
            style={{
              color: colors.textMuted,
              fontSize: 12,
            }}
          >
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
          <div
            style={{
              color: colors.textMuted,
              fontSize: 12,
            }}
          >
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
          <div
            style={{
              color: colors.textMuted,
              fontSize: 12,
            }}
          >
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
          <div
            style={{
              color: colors.textMuted,
              fontSize: 12,
            }}
          >
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
    </div>
  );
}

export default ShipmentStatus;

