import type { Meta, StoryObj } from "@storybook/react-vite";
import { MiniBarChart } from "./MiniBarChart";

const data = [
  { name: "Jan", value: 40 },
  { name: "Feb", value: 65 },
  { name: "Mar", value: 50 },
  { name: "Apr", value: 80 },
  { name: "May", value: 70 },
];

const meta = {
  title: "Charts/MiniBarChart",
  component: MiniBarChart,
  tags: ["autodocs"],
} satisfies Meta<typeof MiniBarChart>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data,
    xKey: "name",
    yKey: "value",
  },
};
