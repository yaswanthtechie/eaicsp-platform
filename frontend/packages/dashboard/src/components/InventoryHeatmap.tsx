import { useEffect, useState } from "react";
import { Badge } from "../../../ui/src/components/Badge";
import { Spinner } from "../../../ui/src/components/Spinner";
import { inventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";

export default function InventoryHeatmap() {
  const [hovered, setHovered] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

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
      <div style={{ color: colors.text }}>
        <h2>Something went wrong in Heatmap Data.</h2>

        <button onClick={() => setError(false)}>
          Retry
        </button>
      </div>
    );
  }

  if (inventory.length === 0) {
    return (
      <h2 style={{ color: colors.text }}>
        No Inventory Heatmap data available.
      </h2>
    );
  }

  const getStatus = (quantity: number, reorder: number) => {
    if (quantity < reorder) {
      return "danger";
    }

    if (quantity < reorder * 1.5) {
      return "warning";
    }

    return "success";
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

  const warehouses = ["WH001", "WH002", "WH003"];

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

            {inventory
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