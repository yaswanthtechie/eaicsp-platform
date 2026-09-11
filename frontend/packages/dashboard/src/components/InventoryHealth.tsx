import { useEffect, useState } from "react";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";
import Skeleton from "./Skeleton";

interface InventoryItem {
  sku_id: string;
  product_name: string;
  warehouse_id: string;
  quantity_on_hand: number;
  reorder_point: number;
  needs_reorder: boolean;
  avg_daily_demand: number;
}

type HealthStatus = "Healthy" | "Low" | "Critical";
type FilterType = HealthStatus | "Reorder";

function getHealthStatus(daysRemaining: number): HealthStatus {
  if (daysRemaining <= 5) return "Critical";
  if (daysRemaining <= 10) return "Low";
  return "Healthy";
}

function InventoryHealth() {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeFilter, setActiveFilter] =
    useState<FilterType | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let mounted = true;

    loadInventory()
      .then((data) => {
        if (mounted) {
          setInventory(data);
          setError(false);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setError(true);
          setLoading(false);
        }
      });

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
        <Skeleton width="30%" height={28} />

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="50%" height={18} />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(4, minmax(0, 1fr))",
            gap: space.sm,
            marginTop: space.md,
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
          Failed to load inventory health.
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

  const healthData = inventory.map((item) => {
    const daysRemaining =
      item.avg_daily_demand > 0
        ? Math.ceil(
            item.quantity_on_hand / item.avg_daily_demand,
          )
        : Infinity;

    return {
      ...item,
      daysRemaining,
      health: getHealthStatus(daysRemaining),
    };
  });

  const healthyCount = healthData.filter(
    (item) => item.health === "Healthy",
  ).length;

  const lowCount = healthData.filter(
    (item) => item.health === "Low",
  ).length;

  const criticalCount = healthData.filter(
    (item) => item.health === "Critical",
  ).length;

  const reorderCount = healthData.filter(
    (item) => item.needs_reorder,
  ).length;

  const filteredItems = activeFilter
    ? healthData.filter((item) =>
        activeFilter === "Reorder"
          ? item.needs_reorder
          : item.health === activeFilter,
      )
    : [];

  const getStatusColor = (status: HealthStatus) => {
    if (status === "Critical") return colors.danger;
    if (status === "Low") return colors.warning;
    return colors.success;
  };

  const handleFilterClick = (filter: FilterType) => {
    setActiveFilter((current) =>
      current === filter ? null : filter,
    );
  };

  const kpis = [
    {
      label: "Healthy",
      value: healthyCount,
      filter: "Healthy" as FilterType,
      color: colors.success,
    },
    {
      label: "Low Stock",
      value: lowCount,
      filter: "Low" as FilterType,
      color: colors.warning,
    },
    {
      label: "Critical",
      value: criticalCount,
      filter: "Critical" as FilterType,
      color: colors.danger,
    },
    {
      label: "Need Reorder",
      value: reorderCount,
      filter: "Reorder" as FilterType,
      color: colors.primary,
    },
  ];

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
      <div style={{ marginBottom: space.md }}>
        <h2
          style={{
            margin: 0,
            color: colors.text,
            fontSize: "20px",
            fontWeight: 600,
          }}
        >
          Inventory Health
        </h2>

        <p
          style={{
            margin: `${space.xs}px 0 0`,
            color: colors.textMuted,
            fontSize: "14px",
          }}
        >
          Click a health metric to view affected inventory
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(4, minmax(0, 1fr))",
          gap: space.sm,
        }}
      >
        {kpis.map((kpi) => {
          const selected = activeFilter === kpi.filter;

          return (
            <button
              key={kpi.filter}
              type="button"
              onClick={() => handleFilterClick(kpi.filter)}
              style={{
                textAlign: "left",
                background: selected
                  ? colors.bg
                  : colors.surface,
                border: `1px solid ${
                  selected ? kpi.color : colors.border
                }`,
                borderRadius: radius.md,
                padding: space.md,
                cursor: "pointer",
                minWidth: 0,
              }}
            >
              <div
                style={{
                  color: colors.textMuted,
                  fontSize: "12px",
                  marginBottom: space.xs,
                }}
              >
                {kpi.label}
              </div>

              <div
                style={{
                  color: kpi.color,
                  fontSize: "24px",
                  fontWeight: 700,
                }}
              >
                {kpi.value}
              </div>
            </button>
          );
        })}
      </div>

      {activeFilter && (
        <div
          style={{
            marginTop: space.md,
            borderTop: `1px solid ${colors.border}`,
            paddingTop: space.md,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: space.sm,
            }}
          >
            <h3
              style={{
                margin: 0,
                color: colors.text,
                fontSize: "15px",
                fontWeight: 600,
              }}
            >
              {activeFilter === "Reorder"
                ? "Items Needing Reorder"
                : `${activeFilter} Inventory`}
            </h3>

            <button
              type="button"
              onClick={() => setActiveFilter(null)}
              style={{
                background: "transparent",
                border: "none",
                color: colors.textMuted,
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              Clear
            </button>
          </div>

          {filteredItems.length === 0 ? (
            <p
              style={{
                color: colors.textMuted,
                fontSize: "13px",
              }}
            >
              No inventory items found.
            </p>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: space.xs,
                maxHeight: "260px",
                overflowY: "auto",
              }}
            >
              {filteredItems.map((item) => (
                <div
                  key={item.sku_id}
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "1.5fr 0.8fr 1fr 0.8fr",
                    gap: space.sm,
                    alignItems: "center",
                    padding: `${space.sm}px ${space.md}px`,
                    border: `1px solid ${colors.border}`,
                    borderRadius: radius.sm,
                  }}
                >
                  <div>
                    <div
                      style={{
                        color: colors.text,
                        fontSize: "13px",
                        fontWeight: 600,
                      }}
                    >
                      {item.product_name}
                    </div>

                    <div
                      style={{
                        color: colors.textMuted,
                        fontSize: "11px",
                      }}
                    >
                      {item.sku_id} · {item.warehouse_id}
                    </div>
                  </div>

                  <div>
                    <div
                      style={{
                        color: colors.textMuted,
                        fontSize: "11px",
                      }}
                    >
                      Stock
                    </div>

                    <div
                      style={{
                        color: colors.text,
                        fontSize: "13px",
                        fontWeight: 600,
                      }}
                    >
                      {item.quantity_on_hand}
                    </div>
                  </div>

                  <div>
                    <div
                      style={{
                        color: colors.textMuted,
                        fontSize: "11px",
                      }}
                    >
                      Days Remaining
                    </div>

                    <div
                      style={{
                        color: colors.text,
                        fontSize: "13px",
                        fontWeight: 600,
                      }}
                    >
                      {Number.isFinite(item.daysRemaining)
                        ? `${item.daysRemaining.toFixed(1)} days`
                        : "N/A"}
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: `${space.xs}px ${space.sm}px`,
                        borderRadius: radius.sm,
                        border: `1px solid ${
                          getStatusColor(item.health)
                        }`,
                        color: getStatusColor(item.health),
                        fontSize: "11px",
                        fontWeight: 600,
                      }}
                    >
                      {item.health}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default InventoryHealth;

