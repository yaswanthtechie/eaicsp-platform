import type { Meta, StoryObj } from "@storybook/react";
import { DataTable, type Column } from "./DataTable";

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
  {
    id: 5,
    name: "Headphones",
    category: "Audio",
    price: 5000,
  },
  {
    id: 6,
    name: "Webcam",
    category: "Accessories",
    price: 3500,
  },
];

const manyProducts: Product[] = Array.from(
  { length: 100 },
  (_, index) => ({
    id: index + 1,
    name: `Product ${index + 1}`,
    category:
      index % 2 === 0
        ? "Electronics"
        : "Accessories",
    price: 1000 + index * 250,
  })
);

const columns: Column<Product>[] = [
  {
    key: "id",
    label: "ID",
    sortable: true,
  },
  {
    key: "name",
    label: "Product",
    sortable: true,
    searchable: true,
  },
  {
    key: "category",
    label: "Category",
    sortable: true,
    searchable: true,
  },
  {
    key: "price",
    label: "Price",
    sortable: true,
  },
];

const meta = {
  title: "Components/DataTable",
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <DataTable<Product>
      data={products}
      columns={columns}
      pageSize={5}
    />
  ),
};

export const Empty: Story = {
  render: () => (
    <DataTable<Product>
      data={[]}
      columns={columns}
      pageSize={5}
    />
  ),
};

export const SortingAndFiltering: Story = {
  render: () => (
    <DataTable<Product>
      data={products}
      columns={columns}
      pageSize={5}
    />
  ),
};

export const Pagination: Story = {
  render: () => (
    <DataTable<Product>
      data={products}
      columns={columns}
      pageSize={2}
    />
  ),
};

export const RowSelection: Story = {
  render: () => (
    <DataTable<Product>
      data={products}
      columns={columns}
      pageSize={5}
      selectableRows
    />
  ),
};

export const OverflowText: Story = {
  render: () => (
    <DataTable<Product>
      data={[
        {
          id: 1,
          name: "This is a very long product name that should test text overflow behavior inside the DataTable",
          category:
            "This is a very long category name that should test horizontal overflow behavior",
          price: 99999,
        },
      ]}
      columns={columns}
      pageSize={5}
    />
  ),
};

export const PerformanceTest: Story = {
  render: () => (
    <DataTable<Product>
      data={manyProducts}
      columns={columns}
      pageSize={20}
      selectableRows
    />
  ),
};