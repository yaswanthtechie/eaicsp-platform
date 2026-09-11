import { useEffect, useState } from "react";
import { List, type RowComponentProps } from "react-window";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";
import type { InventoryItem } from "../types/forecast";
import Skeleton from "./Skeleton";

interface InventoryTableProps {
  shouldFail?: boolean;
  data?: InventoryItem[];
}

interface InventoryRow extends InventoryItem {
  daysRemaining: number;
  expectedOrderDate: Date;
}

interface RowProps {
  items: InventoryRow[];
}

export default function InventoryTable({
  shouldFail = false,
  data,
}: InventoryTableProps) {
  const [inventoryData, setInventoryData] = useState<InventoryItem[]>([]);
  const [showLowStock, setShowLowStock] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (data !== undefined) {
      const timer = setTimeout(() => {
        setInventoryData(data);
        setLoading(false);
        setError(false);
      }, 1000);

      return () => clearTimeout(timer);
    }

    let cancelled = false;

    const fetchInventory = async () => {
      setLoading(true);
      setError(false);

      try {
        const loadedData = await loadInventory(shouldFail);

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

    fetchInventory();

    return () => {
      cancelled = true;
    };
  }, [data, shouldFail, retryCount]);

  if (loading) {
    return (
      <div
        style={{
          padding: space.lg,
          background: colors.surface,
          borderRadius: radius.md,
        }}
      >
        <Skeleton width="35%" height={28} />

        <div
          style={{
            display: "flex",
            gap: space.md,
            marginTop: space.md,
          }}
        >
          <Skeleton width={180} height={36} borderRadius={radius.sm} />
          <Skeleton width={220} height={20} />
        </div>

        <div style={{ marginTop: space.md }}>
          <Skeleton
            width="100%"
            height={400}
            borderRadius={radius.sm}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          minHeight: 350,
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
          color: colors.text,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          textAlign: "center",
        }}
      >
        <h2>Something went wrong in table.</h2>

        <button
          onClick={() => setRetryCount((count) => count + 1)}
          style={{
            padding: "8px 16px",
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
          minHeight: 350,
          background: colors.surface,
          padding: space.md,
          borderRadius: radius.md,
          color: colors.text,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        }}
      >
        <h2>No Inventory Data Available.</h2>
      </div>
    );
  }

  const filteredInventory = inventoryData.filter((item) => {
    if (showLowStock) {
      return item.needs_reorder;
    }

    return true;
  });

  const searchedInventory: InventoryRow[] = filteredInventory
    .filter((item) =>
      item.sku_id.toLowerCase().includes(search.toLowerCase())
    )
    .map((item) => {
      const daysRemaining =
        item.avg_daily_demand > 0
          ? Math.ceil(
              item.quantity_on_hand / item.avg_daily_demand
            )
          : 0;

      const expectedOrderDate = new Date();

      expectedOrderDate.setHours(0, 0, 0, 0);

      expectedOrderDate.setDate(
        expectedOrderDate.getDate() + daysRemaining
      );

      return {
        ...item,
        daysRemaining,
        expectedOrderDate,
      };
    })
    .sort(
      (a, b) =>
        a.expectedOrderDate.getTime() -
        b.expectedOrderDate.getTime()
    );

  const cellStyle = {
    padding: space.sm,
    border: `1px solid ${colors.border}`,
    textAlign: "left" as const,
    whiteSpace: "nowrap" as const,
  };

  const headerStyle = {
    ...cellStyle,
    background: colors.bg,
    color: colors.text,
    fontWeight: 600,
  };

  function Row({
    index,
    style,
    items,
  }: RowComponentProps<RowProps>) {
    const item = items[index];

    return (
      <div
        style={{
          ...style,
          display: "grid",
          gridTemplateColumns:
            "100px 180px 120px 120px 100px 120px 130px 160px 120px",
          color: colors.text,
        }}
      >
        <div style={cellStyle}>{item.sku_id}</div>

        <div style={cellStyle}>{item.product_name}</div>

        <div style={cellStyle}>{item.category}</div>

        <div style={cellStyle}>{item.warehouse_id}</div>

        <div style={cellStyle}>{item.quantity_on_hand}</div>

        <div style={cellStyle}>{item.reorder_point}</div>

        <div style={cellStyle}>
          {item.daysRemaining} days
        </div>

        <div style={cellStyle}>
          {item.expectedOrderDate.toLocaleDateString("en-GB")}
        </div>

        <div
          style={{
            ...cellStyle,
            color: item.needs_reorder
              ? colors.danger
              : colors.success,
            fontWeight: 600,
          }}
        >
          {item.needs_reorder ? "Low Stock" : "In Stock"}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: colors.surface,
        padding: space.md,
        borderRadius: radius.md,
        marginTop: space.sm,
      }}
    >
      <h2
        style={{
          color: colors.text,
          marginTop: 0,
        }}
      >
        Inventory Table
      </h2>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: space.md,
          marginBottom: space.md,
          flexWrap: "wrap",
        }}
      >
        <input
          type="text"
          placeholder="Search SKU"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "8px",
            border: `1px solid ${colors.border}`,
            borderRadius: radius.sm,
            background: colors.bg,
            color: colors.text,
          }}
        />

        <label
          style={{
            color: colors.text,
            display: "flex",
            alignItems: "center",
            gap: space.sm,
          }}
        >
          <input
            type="checkbox"
            checked={showLowStock}
            onChange={(e) => setShowLowStock(e.target.checked)}
          />
          Show only low stock items
        </label>
      </div>

      <div
        style={{
          overflowX: "auto",
          border: `1px solid ${colors.border}`,
          borderRadius: radius.sm,
        }}
      >
        <div style={{ minWidth: 1150 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "100px 180px 120px 120px 100px 120px 130px 160px 120px",
            }}
          >
            <div style={headerStyle}>SKU</div>
            <div style={headerStyle}>Product</div>
            <div style={headerStyle}>Category</div>
            <div style={headerStyle}>Warehouse</div>
            <div style={headerStyle}>Quantity</div>
            <div style={headerStyle}>Reorder Point</div>
            <div style={headerStyle}>Days Remaining</div>
            <div style={headerStyle}>Expected Order Date</div>
            <div style={headerStyle}>Status</div>
          </div>

          <List
            rowComponent={Row}
            rowCount={searchedInventory.length}
            rowHeight={52}
            rowProps={{ items: searchedInventory }}
            style={{ height: 400 }}
          />
        </div>
      </div>

      {searchedInventory.length === 0 && (
        <div
          style={{
            padding: space.md,
            textAlign: "center",
            color: colors.textMuted,
          }}
        >
          SKU Number Not Available
        </div>
      )}
    </div>
  );
}

