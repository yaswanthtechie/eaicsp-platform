import { useState } from "react";

import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { KpiCard } from "../components/KpiCard";
import { KpiGrid } from "../components/KpiGrid";
import { Modal } from "../components/Modal";
import { Tabs, type TabItem } from "../components/Tabs";
import { Toast } from "../components/Toast";
import { Spinner } from "../components/Spinner";
import { AlertBanner } from "../components/AlertBanner";
import { StatusIndicator } from "../components/StatusIndicator";
import { Table, type Column } from "../components/Table";
import { DataTable } from "../components/DataTable";
import type { Column as DataTableColumn } from "../components/DataTable";


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


const tableColumns: Column<Inventory>[] = [
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


const dataTableColumns: DataTableColumn<Inventory>[] = [
  {
    key: "product",
    label: "Product",
    sortable: true,
    searchable: true,
  },
  {
    key: "stock",
    label: "Stock",
    sortable: true,
  },
  {
    key: "status",
    label: "Status",
    searchable: true,
  },
];


const tabs: TabItem[] = [
  {
    value: "overview",
    label: "Overview",
    content: <p>Welcome to dashboard overview.</p>,
  },
  {
    value: "products",
    label: "Products",
    content: <p>Manage products here.</p>,
  },
  {
    value: "settings",
    label: "Settings",
    content: <p>Configure settings here.</p>,
  },
];


const kpis = [
  {
    label: "Revenue",
    value: "₹5.2M",
    delta: 5.4,
  },
  {
    label: "Orders",
    value: 356,
    delta: 8,
  },
  {
    label: "Inventory",
    value: 120,
    delta: -3.5,
  },
];


export function DocsPage() {

  const [isModalOpen, setIsModalOpen] =
    useState(false);

  const [showToast, setShowToast] =
    useState(false);


  return (
    <div
      style={{
        padding: "30px",
        display: "flex",
        flexDirection: "column",
        gap: "30px",
      }}
    >

      <h1>
        UI Component Library Documentation
      </h1>

      <p>
        Reusable React + TypeScript components
        for dashboard applications.
      </p>


      <hr />


      <h2>Button</h2>

      <Button
        variant="primary"
        size="md"
      >
        Primary
      </Button>


      <h2>Card</h2>

      <Card title="Inventory Summary">
        <p>
          Card component example.
        </p>
      </Card>


      <h2>Badge</h2>

      <div>
        <Badge status="success">
          Success
        </Badge>

        <Badge status="warning">
          Warning
        </Badge>

        <Badge status="danger">
          Danger
        </Badge>
      </div>


      <h2>Status Indicator</h2>

      <StatusIndicator
        status="online"
        label="Online"
      />


      <h2>KPI Card</h2>

      <KpiCard
        label="Revenue"
        value="₹5.2M"
        delta={5}
      />


      <h2>KPI Grid</h2>

      <KpiGrid
        items={kpis}
        columns={2}
      />


      <h2>Modal</h2>

      <Button
        variant="primary"
        onClick={() =>
          setIsModalOpen(true)
        }
      >
        Open Modal
      </Button>


      <Modal
        isOpen={isModalOpen}
        title="Example Modal"
        onClose={() =>
          setIsModalOpen(false)
        }
      >
        <p>
          Modal content
        </p>
      </Modal>


      <h2>Tabs</h2>

      <Tabs items={tabs} />


      <h2>Toast</h2>

      <Button
        variant="primary"
        onClick={() =>
          setShowToast(true)
        }
      >
        Show Toast
      </Button>


      {showToast && (
        <Toast
          id={1}
          title="Success"
          description="Saved successfully"
          variant="success"
          onClose={() =>
            setShowToast(false)
          }
        />
      )}


      <h2>Spinner</h2>

      <Spinner size="md" />


      <h2>Alert Banner</h2>

      <AlertBanner
        type="warning"
        title="Low Stock"
        message="Some products are low."
      />


      <h2>Table</h2>

      <Table
        columns={tableColumns}
        data={inventoryData}
        rowKey={(row) =>
          row.product
        }
      />


      <h2>Data Table</h2>

      <DataTable
        columns={dataTableColumns}
        data={inventoryData}
        rowKey={(row) =>
          row.product
        }
      />

    </div>
  );
}