import { useState } from "react";
import {
  Button,
  Badge,
  Card,
  DataTable,
  Modal,
  TrendLine,
} from "@eaicsp/ui";

type Product = {
  id: number;
  name: string;
  category: string;
  price: number;
};

const products: Product[] = [
  {
    id: 1,
    name: "Laptop",
    category: "Electronics",
    price: 75000,
  },
  {
    id: 2,
    name: "Keyboard",
    category: "Accessories",
    price: 2500,
  },
  {
    id: 3,
    name: "Monitor",
    category: "Electronics",
    price: 18000,
  },
  {
    id: 4,
    name: "Mouse",
    category: "Accessories",
    price: 1200,
  },
];

const columns = [
  {
    key: "id" as const,
    label: "ID",
    sortable: true,
  },
  {
    key: "name" as const,
    label: "Product",
    sortable: true,
    searchable: true,
  },
  {
    key: "category" as const,
    label: "Category",
    sortable: true,
    searchable: true,
  },
  {
    key: "price" as const,
    label: "Price",
    sortable: true,
  },
];

const salesData = [
  {
    month: "Jan",
    sales: 120,
  },
  {
    month: "Feb",
    sales: 180,
  },
  {
    month: "Mar",
    sales: 150,
  },
  {
    month: "Apr",
    sales: 220,
  },
];

function App() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <main
      style={{
        padding: "30px",
        maxWidth: "1200px",
        margin: "0 auto",
      }}
    >
      <h1>EAICSP UI Library</h1>

      <p>
        This application is importing components from{" "}
        <strong>@eaicsp/ui</strong>.
      </p>

      <hr />

      <section>
        <h2>Button</h2>

        <Button
          variant="primary"
          onClick={() => setIsModalOpen(true)}
        >
          Open Modal
        </Button>
      </section>

      <section>
        <h2>Badge</h2>

        <Badge status="success">
          Active
        </Badge>
      </section>

      <section>
        <h2>Card</h2>

        <Card>
          <h3>Dashboard Card</h3>
          <p>
            This Card is imported from the EAICSP UI
            library.
          </p>
        </Card>
      </section>

      <section>
        <h2>DataTable</h2>

        <DataTable<Product>
          data={products}
          columns={columns}
          pageSize={3}
          selectableRows
        />
      </section>

      <section>
        <h2>Trend Line</h2>

        <TrendLine
          data={salesData}
          xKey="month"
          yKey="sales"
        />
      </section>

      <Modal
        isOpen={isModalOpen}
        title="UI Library Modal"
        onClose={() => setIsModalOpen(false)}
      >
        <p>
          This Modal is imported from
          <strong> @eaicsp/ui</strong>.
        </p>
      </Modal>
    </main>
  );
}

export default App;
