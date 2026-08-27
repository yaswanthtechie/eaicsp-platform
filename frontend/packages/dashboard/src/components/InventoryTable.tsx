import { useEffect, useState } from "react";
import { Badge } from "../../../ui/src/components/Badge";
import { Table } from "../../../ui/src/components/Table";
import { inventory } from "../mocks/inventory";
import { colors, space } from "../tokens";

export default function InventoryTable() {
  const [showLowStock, setShowLowStock] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);

    return () => clearTimeout(timer);
  }, []);

  if (error) {
    return (
      <div>
        <h2 style={{ color: colors.text }}>
          Something went wrong in table.
        </h2>

        <button onClick={() => setError(false)}>
          Retry
        </button>
      </div>
    );
  }

  const filteredInventory = inventory.filter((item) => {
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
      key: "sku_id" as keyof (typeof inventory)[number],
      header: "SKU"
    },
    {
      key: "product_name" as keyof (typeof inventory)[number],
      header: "Product"
    },
    {
      key: "warehouse_id" as keyof (typeof inventory)[number],
      header: "Warehouse"
    },
    {
      key: "quantity_on_hand" as keyof (typeof inventory)[number],
      header: "Quantity"
    },
    {
      key: "reorder_point" as keyof (typeof inventory)[number],
      header: "Reorder Point",
    },
    {
      key: "needs_reorder" as keyof (typeof inventory)[number],
      header: "Status",
      render: (item: (typeof inventory)[number]) =>
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
        borderRadius: 10,
        marginTop: space.sm
      }}
    >
      <h2
        style={{
          color: colors.text,
          marginTop: 0
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
          textAlign:"left"
        }}
      />

      <label
        style={{
          color: colors.text,
          display: "flex",
          gap: space.sm,
          marginBottom: space.md
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
          loading={loading}
          emptyMessage="SKU Number Not Available"
        />
      </div>
    </div>
  );
}