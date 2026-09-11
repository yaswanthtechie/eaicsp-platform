import type { Meta, StoryObj } from "@storybook/react-vite";
import { Badge } from "./Badge";

const meta = {
  title: "Components/Badge",
  component: Badge,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  argTypes: {
    status: {
      control: "select",
      options: ["info", "success", "warning", "danger", "neutral"],
    },
  },
} satisfies Meta<typeof Badge>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Info: Story = {
  args: {
    status: "info",
    children: "Information",
  },
};

export const Success: Story = {
  args: {
    status: "success",
    children: "Success",
  },
};

export const Warning: Story = {
  args: {
    status: "warning",
    children: "Warning",
  },
};

export const Danger: Story = {
  args: {
    status: "danger",
    children: "Danger",
  },
};

export const Neutral: Story = {
  args: {
    status: "neutral",
    children: "Neutral",
  },
};