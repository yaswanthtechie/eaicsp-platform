import type { Meta, StoryObj } from "@storybook/react-vite";
import { KpiCard } from "./KpiCard";

const meta = {
  title: "Components/KpiCard",
  component: KpiCard,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  argTypes: {
    delta: {
      control: "number",
    },
  },
} satisfies Meta<typeof KpiCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    label: "Revenue",
    value: "$24,500",
    delta: 12.5,
  },
};

export const PositiveDelta: Story = {
  args: {
    label: "Users",
    value: 1250,
    delta: 8,
  },
};

export const NegativeDelta: Story = {
  args: {
    label: "Conversion Rate",
    value: "3.2%",
    delta: -4.5,
  },
};

export const NoDelta: Story = {
  args: {
    label: "Total Orders",
    value: 842,
  },
};