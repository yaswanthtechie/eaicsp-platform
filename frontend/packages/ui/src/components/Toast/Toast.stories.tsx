import type { Meta, StoryObj } from "@storybook/react-vite";
import { Toast } from "./Toast";

const meta = {
  title: "Components/Toast",
  component: Toast,
  tags: ["autodocs"],
  args: {
    id: 1,
    title: "Changes saved",
    description: "Your changes have been saved successfully.",
    variant: "success",
    duration: 0,
    onClose: () => {},
  },
} satisfies Meta<typeof Toast>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Success: Story = {};

export const Error: Story = {
  args: {
    title: "Something went wrong",
    description: "Please try again.",
    variant: "error",
  },
};

export const Warning: Story = {
  args: {
    title: "Warning",
    description: "Please review your changes.",
    variant: "warning",
  },
};

export const Info: Story = {
  args: {
    title: "Information",
    description: "A new update is available.",
    variant: "info",
  },
};
