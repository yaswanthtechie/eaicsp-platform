import type { Meta, StoryObj } from "@storybook/react-vite";
import { DataTable, type Column } from "./DataTable";

interface User {
  id: number;
  name: string;
  email: string;
  status: string;
}

const data: User[] = [
  {
    id: 1,
    name: "Alice Johnson",
    email: "alice@example.com",
    status: "Active",
  },
  {
    id: 2,
    name: "Bob Smith",
    email: "bob@example.com",
    status: "Active",
  },
  {
    id: 3,
    name: "Charlie Brown",
    email: "charlie@example.com",
    status: "Pending",
  },
  {
    id: 4,
    name: "Diana Wilson",
    email: "diana@example.com",
    status: "Inactive",
  },
  {
    id: 5,
    name: "Ethan Davis",
    email: "ethan@example.com",
    status: "Active",
  },
];

const columns: Column<User>[] = [
  {
    key: "name",
    label: "Name",
    sortable: true,
    searchable: true,
  },
  {
    key: "email",
    label: "Email",
    searchable: true,
  },
  {
    key: "status",
    label: "Status",
    sortable: true,
    searchable: true,
  },
];

const meta: Meta<typeof DataTable<User>> = {
  title: "Components/DataTable",
  component: DataTable,
  parameters: {
    layout: "padded",
  },
  tags: ["autodocs"],
};

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data,
    columns,
    pageSize: 5,
    rowKey: (row) => row.id,
  },
};

export const Selectable: Story = {
  args: {
    data,
    columns,
    pageSize: 5,
    selectableRows: true,
    rowKey: (row) => row.id,
  },
};