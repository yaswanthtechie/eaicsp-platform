import type { Meta, StoryObj } from "@storybook/react-vite";
import { Table } from "./Table";

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
}

const data: User[] = [
  {
    id: 1,
    name: "Alice Johnson",
    email: "alice@example.com",
    role: "Admin",
  },
  {
    id: 2,
    name: "Bob Smith",
    email: "bob@example.com",
    role: "Editor",
  },
  {
    id: 3,
    name: "Carol Williams",
    email: "carol@example.com",
    role: "Viewer",
  },
];

const columns = [
  { key: "name" as keyof User, header: "Name" },
  { key: "email" as keyof User, header: "Email" },
  { key: "role" as keyof User, header: "Role" },
];

const meta = {
  title: "Components/Table",
  component: Table,
  tags: ["autodocs"],
} satisfies Meta<typeof Table>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    columns: columns as never,
    data: data as never,
    rowKey: ((row: User) => row.id) as never,
  },
};

export const Empty: Story = {
  args: {
    columns: columns as never,
    data: [] as never,
    rowKey: ((row: User) => row.id) as never,
    emptyMessage: "No users found",
  },
};

export const Loading: Story = {
  args: {
    columns: columns as never,
    data: [] as never,
    rowKey: ((row: User) => row.id) as never,
    loading: true,
  },
};