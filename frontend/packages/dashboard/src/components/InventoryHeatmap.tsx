import { memo, useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { List, type RowComponentProps } from "react-window";
import { dashboardApi } from "../api/dashboard";
import { colors, radius, space } from "../tokens";
import type { InventoryItem } from "../types/forecast";
import Skeleton from "./Skeleton";

interface InventoryHeatmapProps {
  shouldFail?: boolean;
  data?: InventoryItem[];
}

interface CategorySummary {
  category: string;
  quantity: number;
  reorderPoint: number;
  status: string;
  items: InventoryItem[];
}

interface InventoryItemRowProps {
  items: InventoryItem[];
  getStatusColor: (status: string) => string;
  getStatus: (
    quantity: number,
    reorderPoint: number
  ) => string;
  hovered: string | null;
  setHovered: (sku: string | null) => void;
}

function InventoryItemRow({
  index,
  style,
  items,
  getStatusColor,
  getStatus,
  hovered,
  setHovered,
}: RowComponentProps<InventoryItemRowProps>) {
  const item = items[index];

  if (!item) {
    return null;
  }

  const itemStatus = getStatus(
    item.quantity_on_hand,
    item.reorder_point
  );

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if(event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setHovered(item.sku_id);
    }

    if(event.key === "Escape") {
      event.preventDefault();
      setHovered(null);
    }
  };

  return (
    <div
      style={{
        ...style,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: `0 ${space.xs}px`,
        fontSize: 11,
        color:
          hovered === item.sku_id
            ? colors.text
            : colors.textMuted,
        background:
          hovered === item.sku_id
            ? colors.bg
            : "transparent",
        borderRadius: radius.sm,
        cursor: "pointer",
        boxSizing: "border-box",

        outline:
          hovered === item.sku_id
            ? `2px solid ${colors.primary}`
            : "none",
        outlineOffset: -2
      }}
      role="button"
      tabIndex={0}
      aria-label={`SKU ${item.sku_id}, ${item.product_name}, stock ${item.quantity_on_hand}, reorder point ${item.reorder_point}`}
      onMouseEnter={() => setHovered(item.sku_id)}
      onMouseLeave={() => setHovered(null)}
      onFocus={() => setHovered(item.sku_id)}
      onKeyDown={handleKeyDown}
    >
      <span>{item.sku_id}</span>

      <span
        style={{
          color: getStatusColor(itemStatus),
          fontWeight: 600,
        }}
      >
        {item.quantity_on_hand}
      </span>
    </div>
  );
}

function InventoryHeatmap({
  shouldFail = false,
  data,
}: InventoryHeatmapProps) {
  const [inventoryData, setInventoryData] =
    useState<InventoryItem[]>([]);

  const [hovered, setHovered] =
    useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      setError(false);

      try {
        if (data !== undefined) {
          if (!cancelled) {
            setInventoryData(data);
            setLoading(false);
          }

          return;
        }

        const loadedData =
          await dashboardApi.fetchInventory(
            shouldFail
          );

        if (!cancelled) {
          setInventoryData(loadedData);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setInventoryData([]);
          setError(true);
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [shouldFail, retryCount, data]);

  const getStatus = useCallback((
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
  },[]);

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

  const getStatusColor = useCallback((status: string) => {
    if (status === "danger") {
      return colors.danger;
    }

    if (status === "warning") {
      return colors.warning;
    }

    return colors.success;
  },[]);

  const warehouseSummaries = useMemo(() => {
    const warehouseMap = new Map<
      string,
      Map<string, InventoryItem[]>
    >();

    inventoryData.forEach((item) => {
      let categoryMap =
        warehouseMap.get(item.warehouse_id);

      if (!categoryMap) {
        categoryMap = new Map<
          string,
          InventoryItem[]
        >();

        warehouseMap.set(
          item.warehouse_id,
          categoryMap
        );
      }

      let items = categoryMap.get(item.category);

      if (!items) {
        items = [];

        categoryMap.set(item.category, items);
      }

      items.push(item);
    });

    return Array.from(warehouseMap.entries()).map(
      ([warehouse, categoryMap]) => {
        const categories: CategorySummary[] =
          Array.from(categoryMap.entries()).map(
            ([category, items]) => {
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

              return {
                category,
                quantity,
                reorderPoint,
                status: getStatus(
                  quantity,
                  reorderPoint
                ),
                items,
              };
            }
          );

        return {
          warehouse,
          categories,
        };
      }
    );
  }, [inventoryData,getStatus]);

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
        aria-busy="true"
        aria-label="Loading inventory heatmap"
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
        role="alert"
      >
        <h3>Failed to load inventory data.</h3>

        <button
          onClick={() =>
            setRetryCount((count) => count + 1)
          }
          style={{
            padding: `${space.sm}px ${space.md}px`,
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
        role="status"
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
        {warehouseSummaries.map(
          ({ warehouse, categories }) => {
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
                          colors.dangerAlpha12,
                        padding: `${space.xs}px ${space.sm}px`,
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
                          colors.successAlpha12,
                        padding: `${space.xs}px ${space.sm}px`,
                        borderRadius: radius.sm,
                      }}
                    >
                      Healthy
                    </span>
                  )}
                </div>

                {categories.map((category) => {
                  const statusColor =
                    getStatusColor(
                      category.status
                    );

                  const percentage =
                    category.reorderPoint > 0
                      ? Math.min(
                          (category.quantity /
                            (category.reorderPoint *
                              2)) *
                            100,
                          100
                        )
                      : 100;

                  const listHeight = Math.min(
                    category.items.length * 32,
                    192
                  );

                  const hoveredItem =
                    category.items.find(
                      (item) =>
                        item.sku_id === hovered
                    );

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
                          marginBottom: space.xs,
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
                          background:
                            colors.border,
                          borderRadius: radius.sm,
                          overflow: "hidden",
                          marginBottom: space.xs,
                        }}
                      >
                        <div
                          style={{
                            width: `${percentage}%`,
                            height: "100%",
                            background: statusColor,
                            borderRadius: radius.sm,
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
                        <List
                          rowCount={
                            category.items.length
                          }
                          rowHeight={32}
                          rowComponent={
                            InventoryItemRow
                          }
                          rowProps={{
                            items: category.items,
                            getStatusColor,
                            getStatus,
                            hovered,
                            setHovered,
                          }}
                          overscanCount={5}
                          style={{
                            height: listHeight,
                            width: "100%",
                          }}
                        />

                        {hoveredItem && (
                          <div
                            style={{
                              marginTop: space.sm,
                              padding: space.sm,
                              background: colors.bg,
                              border: `1px solid ${colors.border}`,
                              borderRadius: radius.sm,
                              fontSize: 11,
                              lineHeight: 1.5,
                            }}
                            role="status"
                            aria-live="polite"
                          >
                            <div>
                              SKU: {hoveredItem.sku_id}
                            </div>

                            <div>
                              Product:{" "}
                              {
                                hoveredItem.product_name
                              }
                            </div>

                            <div>
                              Category:{" "}
                              {hoveredItem.category}
                            </div>

                            <div>
                              Stock:{" "}
                              {
                                hoveredItem.quantity_on_hand
                              }
                            </div>

                            <div>
                              Reorder Point:{" "}
                              {
                                hoveredItem.reorder_point
                              }
                            </div>

                            <div>
                              Days Remaining:{" "}
                              {hoveredItem.avg_daily_demand >
                              0
                                ? Math.ceil(
                                    hoveredItem.quantity_on_hand /
                                      hoveredItem.avg_daily_demand
                                  )
                                : 0}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          }
        )}
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
              marginRight: space.xs,
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
              marginRight: space.xs,
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
              marginRight: space.xs,
            }}
          />
          Needs Reorder
        </span>
      </div>
    </div>
  );
}

export default memo(InventoryHeatmap);