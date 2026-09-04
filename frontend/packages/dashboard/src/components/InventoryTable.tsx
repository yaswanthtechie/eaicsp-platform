import { useEffect, useState } from "react";
import { Badge } from "../../../ui/src/components/Badge";
import { Button } from "../../../ui/src/components/Button";
import { Spinner } from "../../../ui/src/components/Spinner";
import { Table } from "../../../ui/src/components/Table";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";
interface InventoryTableProps {
  shouldFail?: boolean;
}

export default function InventoryTable({
  shouldFail = false,
}: InventoryTableProps) {
  const [inventoryData, setInventoryData] = useState<
    Awaited<ReturnType<typeof loadInventory>>
  >([]);

  const [showLowStock, setShowLowStock] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const fetchInventory = async () => {
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

    fetchInventory();

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
        <span>Loading Inventory Table...</span>
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

        <Button
          variant="danger"
          size="sm"
          onClick={() => setRetryCount((count) => count + 1)}
        >
          Retry
        </Button>
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

  const searchedInventory = filteredInventory.filter((item) =>
    item.sku_id.toLowerCase().includes(search.toLowerCase())
  );

  const columns = [
    {
      key: "sku_id" as keyof (typeof inventoryData)[number],
      header: "SKU",
    },
    {
      key: "product_name" as keyof (typeof inventoryData)[number],
      header: "Product",
    },
    {
      key: "warehouse_id" as keyof (typeof inventoryData)[number],
      header: "Warehouse",
    },
    {
      key: "quantity_on_hand" as keyof (typeof inventoryData)[number],
      header: "Quantity",
    },
    {
      key: "reorder_point" as keyof (typeof inventoryData)[number],
      header: "Reorder Point",
    },
    {
      key: "needs_reorder" as keyof (typeof inventoryData)[number],
      header: "Status",
      render: (item: (typeof inventoryData)[number]) =>
        item.needs_reorder ? (
          <Badge status="danger">Low Stock</Badge>
        ) : (
          <Badge status="success">In Stock</Badge>
        ),
    },
  ];

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

      <input
        type="text"
        placeholder="Search SKU..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          padding: "8px",
          marginBottom: space.sm,
          textAlign: "left",
        }}
      />

      <label
        style={{
          color: colors.text,
          display: "flex",
          gap: space.sm,
          marginBottom: space.md,
        }}
      >
        <input
          type="checkbox"
          checked={showLowStock}
          onChange={(e) => setShowLowStock(e.target.checked)}
        />

        Show only low stock items
      </label>

      <div style={{ overflowX: "auto" }}>
        <Table
          columns={columns}
          data={searchedInventory}
          rowKey={(item) => item.sku_id}
          loading={false}
          emptyMessage="SKU Number Not Available"
        />
      </div>
    </div>
  );
}