import type { Meta, StoryObj } from "@storybook/react-vite";
import { Sparkline } from "./Sparkline";

const meta = {
  title: "Charts/Sparkline",
  component: Sparkline,
  tags: ["autodocs"],
} satisfies Meta<typeof Sparkline>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data: [
      { value: 20 },
      { value: 35 },
      { value: 28 },
      { value: 50 },
      { value: 42 },
      { value: 65 },
    ],
  },
};

export const Empty: Story = {
  args: {
    data: [],
  },
};
