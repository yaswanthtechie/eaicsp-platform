import { useState } from "react";

import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { Badge } from "./components/Badge";
import { KpiCard } from "./components/KpiCard";
import { Table } from "./components/Table";
import { Modal } from "./components/Modal";
import { Tabs } from "./components/Tabs";
import { Toast } from "./components/Toast";
import { Spinner } from "./components/Spinner";
import type { Column } from "./components/Table";

type Inventory = {
  product: string;
  stock: number;
  status: string;
};

const inventoryData: Inventory[] = [
  {
    product: "Steel Rod",
    stock: 120,
    status: "In Stock",
  },
  {
    product: "Cement",
    stock: 15,
    status: "Low Stock",
  },
  {
    product: "Bricks",
    stock: 0,
    status: "Out of Stock",
  },
];

const columns: Column<Inventory>[] = [
  {
    key: "product",
    header: "Product",
  },
  {
    key: "stock",
    header: "Stock",
  },
  {
    key: "status",
    header: "Status",
    render: (row) => (
      <Badge
        status={
          row.status === "In Stock"
            ? "success"
            : row.status === "Low Stock"
            ? "warning"
            : "danger"
        }
      >
        {row.status}
      </Badge>
    ),
  },
];
const tabs = [
  {
    label: "Overview",
    content: (
      <p>
        Welcome to the dashboard overview.
      </p>
    ),
  },
  {
    label: "Products",
    content: (
      <p>
        Manage all your products here.
      </p>
    ),
  },
  {
    label: "Settings",
    content: (
      <p>
        Configure your application settings.
      </p>
    ),
  },
];
function App() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showToast, setShowToast] = useState(false);

  return (
    <div
      style={{
        padding: "30px",
        display: "flex",
        flexDirection: "column",
        gap: "30px",
      }}
    >
      <h1>Component Showcase</h1>

      {/* Buttons */}

      <h2>Buttons</h2>

      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <Button
          variant="primary"
          size="sm"
          onClick={() => alert("Primary")}
        >
          Primary
        </Button>

        <Button
          variant="secondary"
          size="md"
          onClick={() => alert("Secondary")}
        >
          Secondary
        </Button>

        <Button
          variant="danger"
          size="md"
          onClick={() => alert("Danger")}
        >
          Danger
        </Button>

        <Button
          variant="primary"
          size="md"
          loading
          onClick={() => {}}
        >
          Loading
        </Button>

        <Button
          variant="primary"
          size="md"
          disabled
          onClick={() => {}}
        >
          Disabled
        </Button>
      </div>

      {/* Badges */}

      <h2>Badges</h2>

      <div style={{ display: "flex", gap: "10px" }}>
        <Badge status="success">Success</Badge>
        <Badge status="warning">Warning</Badge>
        <Badge status="danger">Danger</Badge>
        <Badge status="neutral">Neutral</Badge>
      </div>

      {/* KPI Cards */}

      <h2>KPI Cards</h2>

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap" }}>
        <KpiCard
          label="Forecast Accuracy"
          value="92.4%"
          delta={2.1}
        />

        <KpiCard
          label="Revenue"
          value="₹5.2M"
          delta={5.4}
        />

        <KpiCard
          label="Inventory"
          value="120"
          delta={-3.5}
        />
      </div>

      {/* Card */}

      <h2>Card</h2>

      <Card
        title="Inventory"
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => alert("Refresh")}
          >
            Refresh
          </Button>
        }
      >
        <Badge status="success">Healthy</Badge>
      </Card>

      {/* Modal */}

      <h2>Modal</h2>

      <Button
        variant="primary"
        size="md"
        onClick={() => setIsModalOpen(true)}
      >
        Open Modal
      </Button>

      <Modal
        open={isModalOpen}
        title="Delete Product"
        onClose={() => setIsModalOpen(false)}
      >
        <p>
          Are you sure you want to delete this product?
        </p>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
            marginTop: "20px",
          }}
        >
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsModalOpen(false)}
          >
            Cancel
          </Button>

          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              alert("Product Deleted");
              setIsModalOpen(false);
            }}
          >
            Delete
          </Button>
        </div>
      </Modal>
      {/* Tabs */}

<h2>Tabs</h2>

<Tabs tabs={tabs} />
{/* Toast */}

<h2>Toast</h2>

<Button
  variant="primary"
  size="md"
  onClick={() => setShowToast(true)}
>
  Show Toast
</Button>

<Toast
  open={showToast}
  message="Product Saved Successfully!"
  type="success"
  onClose={() => setShowToast(false)}
/>
{/* Spinner */}

<h2>Spinner</h2>

<div
  style={{
    display: "flex",
    gap: "30px",
    alignItems: "center",
  }}
>
  <div>
    <p>Small</p>
    <Spinner size="sm" />
  </div>

  <div>
    <p>Medium</p>
    <Spinner size="md" />
  </div>

  <div>
    <p>Large</p>
    <Spinner size="lg" />
  </div>
</div>

      {/* Table */}

      <h2>Table</h2>

      <Table
        columns={columns}
        data={inventoryData}
        loading={false}
        emptyMessage="Inventory is empty"
      />
    </div>
  );
}

export default App;