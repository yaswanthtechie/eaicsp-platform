import type { Meta, StoryObj } from "@storybook/react-vite";
import { KpiGrid } from "./KpiGrid";

const meta = {
  title: "Components/KpiGrid",
  component: KpiGrid,
  tags: ["autodocs"],
} satisfies Meta<typeof KpiGrid>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    items: [
      { label: "Revenue", value: "$24,500", delta: 12.5 },
      { label: "Users", value: 1248, delta: 8.2 },
      { label: "Orders", value: 326, delta: -3.4 },
      { label: "Conversion", value: "4.8%", delta: 1.2 },
    ],
  },
};

export const Empty: Story = {
  args: {
    items: [],
  },
};
