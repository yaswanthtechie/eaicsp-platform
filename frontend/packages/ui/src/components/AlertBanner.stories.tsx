import type { Meta, StoryObj } from "@storybook/react-vite";
import { AlertBanner } from "./AlertBanner";

const meta = {
  title: "Components/AlertBanner",
  component: AlertBanner,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  argTypes: {
    type: {
      control: "select",
      options: ["info", "success", "warning", "danger"],
    },
  },
} satisfies Meta<typeof AlertBanner>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Info: Story = {
  args: {
    type: "info",
    title: "Information",
    message: "This is an informational alert.",
  },
};

export const Success: Story = {
  args: {
    type: "success",
    title: "Success",
    message: "The operation completed successfully.",
  },
};

export const Warning: Story = {
  args: {
    type: "warning",
    title: "Warning",
    message: "Please review this information before continuing.",
  },
};

export const Danger: Story = {
  args: {
    type: "danger",
    title: "Danger",
    message: "Something went wrong. Please try again.",
  },
};

export const WithAction: Story = {
  args: {
    type: "info",
    title: "Action required",
    message: "Please review the latest information.",
    actionLabel: "Review",
    onAction: () => alert("Review clicked"),
  },
};