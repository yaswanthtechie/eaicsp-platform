import type { Meta, StoryObj } from "@storybook/react-vite";
import { StatusIndicator } from "./StatusIndicator";

const meta = {
  title: "Components/StatusIndicator",
  component: StatusIndicator,
  tags: ["autodocs"],
} satisfies Meta<typeof StatusIndicator>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Online: Story = {
  args: {
    status: "online",
  },
};

export const Offline: Story = {
  args: {
    status: "offline",
  },
};

export const Pending: Story = {
  args: {
    status: "pending",
  },
};

export const Success: Story = {
  args: {
    status: "success",
  },
};

export const Warning: Story = {
  args: {
    status: "warning",
  },
};

export const Error: Story = {
  args: {
    status: "error",
  },
};

export const CustomLabel: Story = {
  args: {
    status: "online",
    label: "System is running",
  },
};
