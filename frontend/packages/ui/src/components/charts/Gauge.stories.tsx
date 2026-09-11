import type { Meta, StoryObj } from "@storybook/react-vite";
import { Gauge } from "./Gauge";

const meta = {
  title: "Charts/Gauge",
  component: Gauge,
  tags: ["autodocs"],
} satisfies Meta<typeof Gauge>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    value: 70,
  },
};

export const Low: Story = {
  args: {
    value: 25,
  },
};

export const High: Story = {
  args: {
    value: 90,
  },
};

export const CustomRange: Story = {
  args: {
    value: 75,
    min: 50,
    max: 100,
    label: "Progress",
  },
};
