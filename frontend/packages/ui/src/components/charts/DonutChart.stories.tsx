import type { Meta, StoryObj } from "@storybook/react-vite";
import { DonutChart } from "./DonutChart";

const data = [
  { name: "Completed", value: 60 },
  { name: "In Progress", value: 25 },
  { name: "Pending", value: 15 },
];

const meta = {
  title: "Charts/DonutChart",
  component: DonutChart,
  tags: ["autodocs"],
} satisfies Meta<typeof DonutChart>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data,
  },
};

export const CustomHeight: Story = {
  args: {
    data,
    height: 400,
  },
};
