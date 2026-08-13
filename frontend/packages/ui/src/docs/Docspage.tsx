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

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

/* =========================================================
   FORM VALIDATION
========================================================= */
const schema = z.object({
  email: z.string().email("Enter a valid email"),
  quantity: z.number().min(1, "Must be at least 1"),
});

type FormValues = z.infer<typeof schema>;

/* =========================================================
   INVENTORY DATA
========================================================= */

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

const longTextInventoryData: Inventory[] = [
  {
    product:
      "Premium Construction Steel Reinforcement Rod — Extremely Long Product Name Example",
    stock: 120,
    status: "In Stock",
  },
  {
    product:
      "High Strength Portland Cement — Very Long Product Description Example",
    stock: 15,
    status: "Low Stock",
  },
];

/* =========================================================
   TABLE COLUMNS
========================================================= */

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

/* =========================================================
   DATA TABLE COLUMNS
========================================================= */

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

/* =========================================================
   TABS
========================================================= */

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

/* =========================================================
   KPI DATA
========================================================= */

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

/* =========================================================
   DOCS PAGE
========================================================= */

export function DocsPage() {
  /*
   * Modal state
   *
   * IMPORTANT:
   * You were missing isModalOpen.
   */
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [isLongModalOpen, setIsLongModalOpen] = useState(false);

  const [showToast, setShowToast] = useState(false);

  /* =======================================================
     REACT HOOK FORM
  ======================================================= */

  const methods = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      quantity: 1,
    },
  });

  const onSubmit = (data: FormValues) => {
    console.log("Form submitted:", data);
  };

  return (
    <div
      style={{
        padding: "30px",
        display: "flex",
        flexDirection: "column",
        gap: "30px",
      }}
    >
      {/* ===================================================
          PAGE HEADER
      =================================================== */}

      <h1>UI Component Library Documentation</h1>

      <p>
        Reusable React + TypeScript components for dashboard applications.
      </p>

      <hr />

      {/* ===================================================
          BUTTON
      =================================================== */}

      <section>
        <h2>Button</h2>

        <Button variant="primary" size="md">
          Primary
        </Button>
      </section>

      {/* ===================================================
          BUTTON - DISABLED EDGE CASE
      =================================================== */}

      <section>
        <h2>Button — Disabled</h2>

        <Button variant="primary" disabled>
          Disabled Button
        </Button>
      </section>

      {/* ===================================================
          CARD
      =================================================== */}

      <section>
        <h2>Card</h2>

        <Card title="Inventory Summary">
          <p>Card component example.</p>
        </Card>
      </section>

      {/* ===================================================
          CARD - OVERFLOW EDGE CASE
      =================================================== */}

      <section>
        <h2>Card — Overflow Text</h2>

        <Card title="Long Content">
          <p
            style={{
              maxWidth: "300px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title="This is a very long piece of text that demonstrates how overflow content is handled inside the Card component."
          >
            This is a very long piece of text that demonstrates how overflow
            content is handled inside the Card component.
          </p>
        </Card>
      </section>

      {/* ===================================================
          BADGE
      =================================================== */}

      <section>
        <h2>Badge</h2>

        <div
          style={{
            display: "flex",
            gap: "10px",
            flexWrap: "wrap",
          }}
        >
          <Badge status="success">Success</Badge>

          <Badge status="warning">Warning</Badge>

          <Badge status="danger">Danger</Badge>
        </div>
      </section>

      {/* ===================================================
          STATUS INDICATOR
      =================================================== */}

      <section>
        <h2>Status Indicator</h2>

        <StatusIndicator status="online" label="Online" />
      </section>

      {/* ===================================================
          KPI CARD
      =================================================== */}

      <section>
        <h2>KPI Card</h2>

        <KpiCard
          label="Revenue"
          value="₹5.2M"
          delta={5}
        />
      </section>

      {/* ===================================================
          KPI GRID
      =================================================== */}

      <section>
        <h2>KPI Grid</h2>

        <KpiGrid
          items={kpis}
          columns={2}
        />
      </section>

      {/* ===================================================
          MODAL
      =================================================== */}

      <section>
        <h2>Modal</h2>

        <p>
          Accessible modal with keyboard navigation, focus management,
          Escape-to-close behavior, and focus restoration.
        </p>

        <Button
          variant="primary"
          onClick={() => setIsModalOpen(true)}
        >
          Open Modal
        </Button>

        <Modal
          isOpen={isModalOpen}
          title="Example Modal"
          onClose={() => setIsModalOpen(false)}
        >
          <p>Modal content.</p>

          <p>
            Press Escape to close the modal and use Tab to move through
            focusable elements.
          </p>
        </Modal>
      </section>

      {/* ===================================================
          MODAL - LONG CONTENT EDGE CASE
      =================================================== */}

      <section>
        <h2>Modal — Long Content</h2>

        <p>
          Long-content modal used to verify scrolling and keyboard
          accessibility.
        </p>

        <Button
          variant="primary"
          onClick={() => setIsLongModalOpen(true)}
        >
          Open Long Content Modal
        </Button>

        <Modal
          isOpen={isLongModalOpen}
          title="Long Content Modal"
          onClose={() => setIsLongModalOpen(false)}
        >
          <div>
            <p>
              This is a long-content example used to verify that the modal
              handles larger amounts of content correctly.
            </p>

            <p>
              Users should be able to navigate through the modal using only
              the keyboard.
            </p>

            <p>
              Press Tab to move through focusable elements.
            </p>

            <p>
              Press Escape to close the modal.
            </p>

            <p>
              When the modal closes, focus should return to the button that
              opened it.
            </p>

            <p>
              Additional content is included here to verify that the modal
              can handle larger amounts of content without breaking the page
              layout.
            </p>

            <p>
              This also helps verify scrolling behavior for long modal
              content.
            </p>

            <p>
              Keyboard users should never become trapped outside the modal
              while it is open.
            </p>
          </div>
        </Modal>
      </section>

      {/* ===================================================
          TABS
      =================================================== */}

      <section>
        <h2>Tabs</h2>

        <p>
          Keyboard navigation: use Tab to reach the tab list and Arrow
          keys to move between tabs.
        </p>

        <Tabs items={tabs} />
      </section>

      {/* ===================================================
          TOAST
      =================================================== */}

      <section>
        <h2>Toast</h2>

        <Button
          variant="primary"
          onClick={() => setShowToast(true)}
        >
          Show Toast
        </Button>

        {showToast && (
          <Toast
            id={1}
            title="Success"
            description="Saved successfully"
            variant="success"
            onClose={() => setShowToast(false)}
          />
        )}
      </section>

      {/* ===================================================
          SPINNER
      =================================================== */}

      <section>
        <h2>Spinner</h2>

        <Spinner size="md" />
      </section>

      {/* ===================================================
          ALERT BANNER
      =================================================== */}

      <section>
        <h2>Alert Banner</h2>

        <AlertBanner
          type="warning"
          title="Low Stock"
          message="Some products are low."
        />
      </section>

      {/* ===================================================
          TABLE
      =================================================== */}

      <section>
        <h2>Table</h2>

        <Table
          columns={tableColumns}
          data={inventoryData}
          rowKey={(row) => row.product}
        />
      </section>

      {/* ===================================================
          DATA TABLE - NORMAL
      =================================================== */}

      <section>
        <h2>Data Table</h2>

        <p>
          Supports sorting, filtering/searching, pagination, and row
          interactions.
        </p>

        <DataTable
          columns={dataTableColumns}
          data={inventoryData}
          rowKey={(row) => row.product}
        />
      </section>

      {/* ===================================================
          DATA TABLE - EMPTY STATE
      =================================================== */}

      <section>
        <h2>Data Table — Empty State</h2>

        <DataTable
          columns={dataTableColumns}
          data={[]}
          rowKey={(row) => row.product}
        />
      </section>

      {/* ===================================================
          DATA TABLE - OVERFLOW TEXT
      =================================================== */}

      <section>
        <h2>Data Table — Overflow Text</h2>

        <DataTable
          columns={dataTableColumns}
          data={longTextInventoryData}
          rowKey={(row) => row.product}
        />
      </section>

      {/* ===================================================
          DATA TABLE - KEYBOARD ACCESSIBILITY
      =================================================== */}

      <section>
        <h2>Data Table — Keyboard Accessibility</h2>

        <p>
          Use Tab to move through interactive table controls. Use Enter or
          Space where applicable to activate controls.
        </p>

        <DataTable
          columns={dataTableColumns}
          data={inventoryData}
          rowKey={(row) => row.product}
        />
      </section>

      {/* ===================================================
          REACT HOOK FORM + ZOD
      =================================================== */}

      <section>
        <h2>React Hook Form + Zod Validation</h2>

        <form onSubmit={methods.handleSubmit(onSubmit)}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              maxWidth: "300px",
            }}
          >
            <label htmlFor="email">
              Email
            </label>

            <input
              id="email"
              type="email"
              placeholder="Email"
              {...methods.register("email")}
              aria-invalid={
                methods.formState.errors.email ? "true" : "false"
              }
            />

            {methods.formState.errors.email && (
              <span role="alert">
                {methods.formState.errors.email.message}
              </span>
            )}

            <label htmlFor="quantity">
              Quantity
            </label>

            <input
              id="quantity"
              type="number"
              placeholder="Quantity"
              {...methods.register("quantity", {
                valueAsNumber: true,
              })}
              aria-invalid={
                methods.formState.errors.quantity ? "true" : "false"
              }
            />

            {methods.formState.errors.quantity && (
              <span role="alert">
                {methods.formState.errors.quantity.message}
              </span>
            )}

            <Button
              variant="primary"
              type="submit"
            >
              Submit
            </Button>
          </div>
        </form>
      </section>

      {/* ===================================================
          ACCESSIBILITY TEST NOTES
      =================================================== */}

      <section>
        <h2>Accessibility — Keyboard Test</h2>

        <ul>
          <li>
            Modal can be opened using the keyboard.
          </li>

          <li>
            Tab navigation stays within the modal while it is open.
          </li>

          <li>
            Escape closes the modal.
          </li>

          <li>
            Focus returns to the button that opened the modal.
          </li>

          <li>
            Tabs can be reached using keyboard navigation.
          </li>

          <li>
            DataTable controls can be reached without using a mouse.
          </li>

          <li>
            Form fields have associated labels and validation messages.
          </li>

          <li>
            Error messages use role="alert" for assistive technologies.
          </li>
        </ul>
      </section>

      {/* ===================================================
          R4 PERFORMANCE NOTES
      =================================================== */}

      <section>
        <h2>Performance</h2>

        <p>
          DataTable derived sorting and filtering state should be memoized
          using useMemo, and stable child components should use React.memo
          where appropriate.
        </p>

        <p>
          React DevTools Profiler can be used to compare render counts and
          render duration before and after memoization.
        </p>
      </section>

      {/* ===================================================
          END
      =================================================== */}
    </div>
  );
}