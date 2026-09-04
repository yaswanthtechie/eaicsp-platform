import { useEffect, useState } from "react";
import { Badge } from "../../../ui/src/components/Badge";
import { Spinner } from "../../../ui/src/components/Spinner";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";
interface InventoryHeatmapProps {
  shouldFail?: boolean;
}

export default function InventoryHeatmap({
  shouldFail = false,
}: InventoryHeatmapProps) {
  const [inventoryData, setInventoryData] = useState<
    Awaited<ReturnType<typeof loadInventory>>
  >([]);

  const [hovered, setHovered] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      setLoading(true);
      setError(false);

      try {
        const data = await loadInventory(shouldFail);

        if (!cancelled) {
          setInventoryData(data);
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
  }, [shouldFail, retryCount]);

  if (loading) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text,
        }}
      >
        <Spinner size="md" />
        <span>Loading Inventory Heatmap...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          minHeight: 350,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          color: colors.text,
          textAlign: "center",
        }}
      >
        <h2>Something went wrong in Heatmap Data.</h2>

        <button onClick={() => setRetryCount((count) => count + 1)}>
          Retry
        </button>
      </div>
    );
  }

  if (inventoryData.length === 0) {
    return (
      <div style={{ color: colors.text }}>
        <h2>No Inventory Heatmap data available.</h2>
      </div>
    );
  }

  const getStatus = (quantity: number, reorder: number) => {
    if (quantity < reorder) {
      return "danger" as const;
    }

    if (quantity < reorder * 1.5) {
      return "warning" as const;
    }

    return "success" as const;
  };

  const getStatusLabel = (quantity: number, reorder: number) => {
    if (quantity < reorder) {
      return "Low Stock";
    }

    if (quantity < reorder * 1.5) {
      return "Near Reorder";
    }

    return "Healthy";
  };
  const warehouses = [
    ...new Set(inventoryData.map((item) => item.warehouse_id)),
  ];

  return (
    <div
      style={{
        background: colors.surface,
        padding: space.md,
        borderRadius: radius.md,
      }}
    >
      <h2 style={{ color: colors.text }}>
        Warehouse Inventory Heatmap
      </h2>

      <p style={{ color: colors.text }}>
        Check stock levels and identify products that need reordering.
      </p>

      <div className="heatmap-grid">
        {warehouses.map((warehouse) => (
          <div key={warehouse}>
            <h3
              style={{
                color: colors.text,
                textAlign: "center",
              }}
            >
              {warehouse}
            </h3>

            {inventoryData
              .filter((item) => item.warehouse_id === warehouse)
              .map((item) => {
                const status = getStatus(
                  item.quantity_on_hand,
                  item.reorder_point
                );

                const statusLabel = getStatusLabel(
                  item.quantity_on_hand,
                  item.reorder_point
                );

                return (
                  <div
                    key={item.sku_id}
                    onMouseEnter={() => setHovered(item.sku_id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{
                      position: "relative",
                      padding: space.md,
                      border: `1px solid ${colors.border}`,
                      color: colors.text,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span>{item.sku_id}</span>

                    <Badge status={status}>
                      {statusLabel}
                    </Badge>

                    <span>{item.quantity_on_hand}</span>

                    {hovered === item.sku_id && (
                      <div
                        style={{
                          position: "absolute",
                          background: colors.bg,
                          padding: space.sm,
                          borderRadius: radius.sm,
                          top: "100%",
                          left: 0,
                          zIndex: 1,
                        }}
                      >
                        <div>SKU: {item.sku_id}</div>

                        <div>
                          Warehouse: {item.warehouse_id}
                        </div>

                        <div>
                          Product: {item.product_name}
                        </div>

                        <div>
                          Quantity: {item.quantity_on_hand}
                        </div>

                        <div>
                          Reorder Point: {item.reorder_point}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        ))}
      </div>
    </div>
  );
}

