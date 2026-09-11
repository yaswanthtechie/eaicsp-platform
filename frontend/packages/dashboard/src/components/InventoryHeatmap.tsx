import { useEffect, useMemo, useState } from "react";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";
import type { InventoryItem } from "../types/forecast";
import Skeleton from "./Skeleton";

interface InventoryHeatmapProps {
  shouldFail?: boolean;
  data?: InventoryItem[];
}

export default function InventoryHeatmap({
  shouldFail = false,
  data,
}: InventoryHeatmapProps) {
  const [inventoryData, setInventoryData] = useState<InventoryItem[]>([]);
  const [hovered, setHovered] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      setError(false);

      try {
        if (data !== undefined) {
          await new Promise<void>((resolve) => {
            setTimeout(resolve, 1000);
          });

          if (!cancelled) {
            setInventoryData(data);
          }

          return;
        }

        const loadedData = await loadInventory(shouldFail);

        if (!cancelled) {
          setInventoryData(loadedData);
        }
      } catch {
        if (!cancelled) {
          setInventoryData([]);
          setError(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [shouldFail, retryCount, data]);

  const warehouses = useMemo(() => {
    return [
      ...new Set(
        inventoryData.map((item) => item.warehouse_id)
      ),
    ];
  }, [inventoryData]);

  const getStatus = (
    quantity: number,
    reorderPoint: number
  ) => {
    if (quantity < reorderPoint) {
      return "danger";
    }

    if (quantity < reorderPoint * 1.5) {
      return "warning";
    }

    return "success";
  };

  const getStatusLabel = (
    quantity: number,
    reorderPoint: number
  ) => {
    if (quantity < reorderPoint) {
      return "Needs Reorder";
    }

    if (quantity < reorderPoint * 1.5) {
      return "Low Soon";
    }

    return "Healthy";
  };

  const getStatusColor = (status: string) => {
    if (status === "danger") {
      return colors.danger;
    }

    if (status === "warning") {
      return colors.warning;
    }

    return colors.success;
  };

  const getCategorySummary = (
    warehouse: string
  ) => {
    const warehouseItems = inventoryData.filter(
      (item) => item.warehouse_id === warehouse
    );

    const categories = [
      ...new Set(
        warehouseItems.map((item) => item.category)
      ),
    ];

    return categories.map((category) => {
      const items = warehouseItems.filter(
        (item) => item.category === category
      );

      const quantity = items.reduce(
        (total, item) =>
          total + item.quantity_on_hand,
        0
      );

      const reorderPoint = items.reduce(
        (total, item) =>
          total + item.reorder_point,
        0
      );

      const status = getStatus(
        quantity,
        reorderPoint
      );

      return {
        category,
        quantity,
        reorderPoint,
        status,
        items,
      };
    });
  };

  if (loading) {
    return (
      <div
        style={{
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
          border: `1px solid ${colors.border}`,
          color: colors.text,
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <Skeleton width="35%" height={28} />

        <div style={{ marginTop: space.sm }}>
          <Skeleton width="30%" height={16} />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(260px, 1fr))",
            gap: space.md,
            marginTop: space.md,
          }}
        >
          <Skeleton
            width="100%"
            height={220}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={220}
            borderRadius={radius.md}
          />

          <Skeleton
            width="100%"
            height={220}
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
          minHeight: 300,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text,
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          textAlign: "center",
        }}
      >
        <h3>Failed to load inventory data.</h3>

        <button
          onClick={() =>
            setRetryCount((count) => count + 1)
          }
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

  if (inventoryData.length === 0) {
    return (
      <div
        style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: space.md,
          color: colors.textMuted,
        }}
      >
        No Inventory Heatmap data available.
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        padding: space.md,
        borderRadius: radius.md,
        border: `1px solid ${colors.border}`,
        color: colors.text,
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <h2
        style={{
          margin: 0,
          marginBottom: space.xs,
          fontSize: 20,
        }}
      >
        Inventory Heatmap
      </h2>

      <p
        style={{
          marginTop: 0,
          marginBottom: space.md,
          color: colors.textMuted,
          fontSize: 13,
        }}
      >
        Warehouse and category stock health
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(260px, 1fr))",
          gap: space.md,
        }}
      >
        {warehouses.map((warehouse) => {
          const categories =
            getCategorySummary(warehouse);

          const reorderCount = categories.filter(
            (category) =>
              category.status === "danger"
          ).length;

          return (
            <div
              key={warehouse}
              style={{
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
                padding: space.md,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: space.md,
                }}
              >
                <strong
                  style={{
                    fontSize: 16,
                    color: colors.text,
                  }}
                >
                  {warehouse}
                </strong>

                {reorderCount > 0 ? (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: colors.danger,
                      background:
                        "rgba(239, 68, 68, 0.12)",
                      padding: "4px 7px",
                      borderRadius: radius.sm,
                    }}
                  >
                    {reorderCount} Reorder
                  </span>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: colors.success,
                      background:
                        "rgba(16, 185, 129, 0.12)",
                      padding: "4px 7px",
                      borderRadius: radius.sm,
                    }}
                  >
                    Healthy
                  </span>
                )}
              </div>

              {categories.map((category) => {
                const statusColor = getStatusColor(
                  category.status
                );

                const percentage =
                  category.reorderPoint > 0
                    ? Math.min(
                        (category.quantity /
                          (category.reorderPoint * 2)) *
                          100,
                        100
                      )
                    : 100;

                return (
                  <div
                    key={category.category}
                    style={{
                      marginBottom: space.sm,
                      padding: space.sm,
                      background: colors.surface,
                      borderRadius: radius.sm,
                      border: `1px solid ${colors.border}`,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        alignItems: "center",
                        marginBottom: 5,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 500,
                        }}
                      >
                        {category.category}
                      </span>

                      <span
                        style={{
                          fontSize: 12,
                          color: statusColor,
                          fontWeight: 600,
                        }}
                      >
                        {category.quantity} units
                      </span>
                    </div>

                    <div
                      style={{
                        height: 5,
                        background: colors.border,
                        borderRadius: 10,
                        overflow: "hidden",
                        marginBottom: 5,
                      }}
                    >
                      <div
                        style={{
                          width: `${percentage}%`,
                          height: "100%",
                          background: statusColor,
                          borderRadius: 10,
                        }}
                      />
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent:
                          "space-between",
                        fontSize: 11,
                        color: colors.textMuted,
                      }}
                    >
                      <span>
                        Reorder at{" "}
                        {category.reorderPoint}
                      </span>

                      <span
                        style={{
                          color: statusColor,
                        }}
                      >
                        {getStatusLabel(
                          category.quantity,
                          category.reorderPoint
                        )}
                      </span>
                    </div>

                    <div
                      style={{
                        marginTop: space.sm,
                        paddingTop: space.xs,
                        borderTop: `1px solid ${colors.border}`,
                      }}
                    >
                      {category.items.map((item) => {
                        const daysRemaining =
                          item.avg_daily_demand > 0
                            ? Math.ceil(
                                item.quantity_on_hand /
                                  item.avg_daily_demand
                              )
                            : 0;

                        const expectedOrderDate =
                          new Date();

                        expectedOrderDate.setHours(
                          0,
                          0,
                          0,
                          0
                        );

                        expectedOrderDate.setDate(
                          expectedOrderDate.getDate() +
                            daysRemaining
                        );

                        const formattedOrderDate =
                          expectedOrderDate.toLocaleDateString(
                            "en-GB"
                          );

                        const itemStatus =
                          getStatus(
                            item.quantity_on_hand,
                            item.reorder_point
                          );

                        return (
                          <div
                            key={item.sku_id}
                            onMouseEnter={() =>
                              setHovered(
                                item.sku_id
                              )
                            }
                            onMouseLeave={() =>
                              setHovered(null)
                            }
                            style={{
                              position: "relative",
                              display: "flex",
                              justifyContent:
                                "space-between",
                              alignItems: "center",
                              padding: "5px 0",
                              fontSize: 11,
                              color:
                                colors.textMuted,
                              cursor: "default",
                            }}
                          >
                            <span>
                              {item.sku_id}
                            </span>

                            <span
                              style={{
                                color:
                                  getStatusColor(
                                    itemStatus
                                  ),
                              }}
                            >
                              {
                                item.quantity_on_hand
                              }
                            </span>

                            {hovered ===
                              item.sku_id && (
                              <div
                                style={{
                                  position:
                                    "absolute",
                                  bottom:
                                    "calc(100% + 5px)",
                                  left: 0,
                                  zIndex: 100,
                                  minWidth: 220,
                                  padding: space.sm,
                                  background:
                                    colors.bg,
                                  color:
                                    colors.text,
                                  border: `1px solid ${colors.border}`,
                                  borderRadius:
                                    radius.sm,
                                  boxShadow:
                                    "0 4px 12px rgba(0,0,0,0.3)",
                                  lineHeight: 1.5,
                                  pointerEvents:
                                    "none",
                                }}
                              >
                                <div>
                                  SKU:{" "}
                                  {item.sku_id}
                                </div>

                                <div>
                                  Product:{" "}
                                  {
                                    item.product_name
                                  }
                                </div>

                                <div>
                                  Category:{" "}
                                  {item.category}
                                </div>

                                <div>
                                  Stock:{" "}
                                  {
                                    item.quantity_on_hand
                                  }
                                </div>

                                <div>
                                  Reorder Point:{" "}
                                  {
                                    item.reorder_point
                                  }
                                </div>

                                <div>
                                  Days Remaining:{" "}
                                  {daysRemaining}
                                </div>

                                <div>
                                  Expected Order:{" "}
                                  {
                                    formattedOrderDate
                                  }
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <div
        style={{
          display: "flex",
          gap: space.md,
          marginTop: space.md,
          flexWrap: "wrap",
          fontSize: 11,
          color: colors.textMuted,
        }}
      >
        <span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: colors.success,
              marginRight: 5,
            }}
          />
          Healthy
        </span>

        <span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: colors.warning,
              marginRight: 5,
            }}
          />
          Low Soon
        </span>

        <span>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: colors.danger,
              marginRight: 5,
            }}
          />
          Needs Reorder
        </span>
      </div>
    </div>
  );
}