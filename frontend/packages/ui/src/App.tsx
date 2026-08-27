import { useState } from "react";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { Badge } from "./components/Badge";
import { KpiCard } from "./components/KpiCard";
import type { Column as TableColumn } from "./components/Table";
import type { Column as DataTableColumn } from "./components/DataTable";
import { Modal } from "./components/Modal";
import type { TabItem } from "./components/Tabs";
import { Tabs } from "./components/Tabs";
import { Toast } from "./components/Toast";
import { Spinner } from "./components/Spinner";
import { KpiGrid } from "./components/KpiGrid";
import { AlertBanner } from "./components/AlertBanner";
import { DataTable } from "./components/DataTable";
import { StatusIndicator } from "./components/StatusIndicator";
import { Table } from "./components/Table";
import { TrendLine } from "./components/charts/TrendLine";
import { MiniBarChart } from "./components/charts/MiniBarChart";
import { Sparkline } from "./components/charts/Sparkline";
import { Gauge } from "./components/charts/Gauge";


type Inventory = {
  product: string;
  stock: number;
  status: string;
};

const productNames = [
  "Samsung Galaxy S24",
  "Apple iPhone 15",
  "Sony WH-1000XM5 Headphones",
  "Dell Inspiron 15 Laptop",
  "HP Pavilion Laptop",
  "Logitech MX Master 3S",
  "Apple AirPods Pro",
  "JBL Flip 6 Speaker",
  "Canon EOS R50 Camera",
  "Amazon Echo Dot",
  "Kindle Paperwhite",
  "Samsung 55-inch Smart TV",
  "LG 27-inch Monitor",
  "Anker Power Bank",
  "Nike Air Max Shoes",
];

const salesData = [
  { month: "Jan", sales: 120 },
  { month: "Feb", sales: 150 },
  { month: "Mar", sales: 180 },
  { month: "Apr", sales: 160 },
  { month: "May", sales: 210 },
];

const inventoryData: Inventory[] = Array.from(
  { length: 50 },
  (_, index) => ({
    product: `${productNames[index % productNames.length]} - ${index + 1}`,
    stock: (index * 17) % 200,
    status:
      index % 3 === 0
        ? "In Stock"
        : index % 3 === 1
          ? "Low Stock"
          : "Out of Stock",
  })
);

const tableColumns: TableColumn<Inventory>[] = [
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
    content: <p>Welcome to the dashboard overview.</p>,
  },
  {
    value: "products",
    label: "Products",
    content: <p>Manage all your products here.</p>,
  },
  {
    value: "settings",
    label: "Settings",
    content: <p>Configure your application settings.</p>,
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
  {
    label: "Forecast Accuracy",
    value: "92.4%",
    delta: 2.1,
  },
];

function App() {
  const [performanceTest, setPerformanceTest] = useState(0);
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
      <h1>UI Component Library Documentation</h1>

      <p>
        A reusable React + TypeScript component library built for dashboard
        applications. Each section below contains a live example, supported
        variants, and usage guidance.
      </p>

      <hr />

      {/* Button */}
      <h2>Button</h2>

      <p>
        A reusable button component used for user actions. It supports
        different variants, sizes, loading, and disabled states.
      </p>

      <div
        style={{
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
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

      {/* Card */}
      <h2>Card</h2>

      <p>
        A reusable container for grouping related content.
      </p>

      <Card
        title="Inventory Summary"
        actions={
          <Button
            variant="primary"
            size="sm"
            onClick={() => alert("View Details")}
          >
            View
          </Button>
        }
      >
        <p>
          This card displays reusable content with a title, actions, and body.
        </p>
      </Card>

      {/* Status Indicator */}
      <h2>Status Indicator</h2>

      <p>
        Shows the current status using a colored indicator.
      </p>

      <div
        style={{
          display: "flex",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <StatusIndicator status="online" label="Online" />
        <StatusIndicator status="pending" label="Pending" />
        <StatusIndicator status="offline" label="Offline" />
        <StatusIndicator status="success" label="Completed" />
        <StatusIndicator status="warning" label="Warning" />
        <StatusIndicator status="error" label="Failed" />
      </div>

      {/* Badge */}
      <h2>Badge</h2>

      <p>
        Displays status labels such as success, warning, danger, and neutral.
      </p>

      <div
        style={{
          display: "flex",
          gap: "10px",
        }}
      >
        <Badge status="success">Success</Badge>
        <Badge status="warning">Warning</Badge>
        <Badge status="danger">Danger</Badge>
        <Badge status="neutral">Neutral</Badge>
      </div>

      {/* KPI Card */}
      <h2>KPI Card</h2>

      <p>
        Displays a single key performance indicator with an optional
        percentage change.
      </p>

      <div
        style={{
          display: "flex",
          gap: "20px",
          flexWrap: "wrap",
        }}
      >
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

      {/* KPI Grid */}
      <h2>KPI Grid</h2>

      <p>
        Arranges multiple KPI cards in a responsive grid layout.
      </p>

      <KpiGrid
        items={kpis}
        columns={2}
      />

      {/* Modal */}
      <h2>Modal</h2>

      <p>
        Displays content in an accessible dialog window.
      </p>

      <Button
        variant="primary"
        size="md"
        onClick={() => setIsModalOpen(true)}
      >
        Open Modal
      </Button>

      <Modal
        isOpen={isModalOpen}
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

      <p>
        Organizes content into multiple tab panels.
      </p>

      <Tabs items={tabs} />

      {/* Toast */}
      <h2>Toast</h2>

      <p>
        Displays temporary notification messages.
      </p>

      <Button
        variant="primary"
        size="md"
        onClick={() => setShowToast(true)}
      >
        Show Toast
      </Button>

      {showToast && (
        <Toast
          id={1}
          title="Product Saved Successfully!"
          description="The product has been saved successfully."
          variant="success"
          onClose={() => setShowToast(false)}
        />
      )}

      {/* Spinner */}
      <h2>Spinner</h2>

      <p>
        Indicates loading or processing state.
      </p>

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

      {/* Alert Banner */}
      <h2>Alert Banner</h2>

      <p>
        Highlights important messages and optional actions.
      </p>

      <AlertBanner
        type="warning"
        title="Inventory Running Low"
        message="Some products are below the minimum stock level."
        actionLabel="View Inventory"
        onAction={() => alert("Opening Inventory")}
      />

      <div style={{ height: 16 }} />

      <AlertBanner
        type="success"
        title="Backup Completed"
        message="Today's backup completed successfully."
      />

      <div style={{ height: 16 }} />

      <AlertBanner
        type="danger"
        title="Server Offline"
        message="The reporting server is currently unavailable."
      />

      <div style={{ height: 16 }} />

      <AlertBanner
        type="info"
        title="New Update Available"
        message="Version 2.0 is ready to install."
        actionLabel="Update"
        onAction={() => alert("Updating...")}
      />

      {/* Table */}
      <h2>Table</h2>

      <p>
        Displays tabular data with customizable columns.
      </p>

      <Table
        columns={tableColumns}
        data={inventoryData}
        rowKey={(row) => row.product}
        loading={false}
        emptyMessage="Inventory is empty"
      />

      {/* Data Table */}
      <h2>Data Table</h2>

      <p>
        Extends the table with sorting, filtering, pagination, and row
        selection.
      </p>
<Button
  variant="secondary"
  size="sm"
  onClick={() => setPerformanceTest((value) => value + 1)}
>
  Test Re-render: {performanceTest}
</Button>

<DataTable
  columns={dataTableColumns}
  data={inventoryData}
  rowKey={(row) => row.product}
  selectableRows
/>

      {/* Data Visualization */}
      <h2>Data Visualization</h2>

      <p>
        Reusable charts for displaying trends and comparing data.
      </p>

      {/* Trend Line */}
      <h3>Trend Line</h3>

      <p>
        Shows how sales change over time.
      </p>

      <TrendLine
        data={salesData}
        xKey="month"
        yKey="sales"
      />
      <h3>Mini Bar Chart</h3>

<p>
  Displays sales values using compact bars for easy comparison.
</p>

<MiniBarChart
  data={salesData}
  xKey="month"
  yKey="sales"
/>
<h3>Sparkline</h3>

<p>
  Displays a compact trend for quick data visualization.
</p>

<Sparkline
  data={[
    { value: 20 },
    { value: 35 },
    { value: 28 },
    { value: 45 },
    { value: 40 },
    { value: 60 },
  ]}
/>

<h3>Gauge</h3>

<p>
  Displays a value relative to a defined range.
</p>

<Gauge
  value={75}
  min={0}
  max={100}
  label="Performance"
/>
    </div>
  );
}

export default App;