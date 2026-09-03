import type { Meta, StoryObj } from "@storybook/react-vite";
import { TrendLine } from "./TrendLine";

type TrendLineData = {
  month: string;
  value: number;
};

const data: TrendLineData[] = [
  { month: "Jan", value: 120 },
  { month: "Feb", value: 180 },
  { month: "Mar", value: 150 },
  { month: "Apr", value: 230 },
  { month: "May", value: 210 },
  { month: "Jun", value: 280 },
];

const meta = {
  title: "Charts/TrendLine",
  component: TrendLine,
  tags: ["autodocs"],
} satisfies Meta<typeof TrendLine>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    data,
    xKey: "month" as never,
    yKey: "value" as never,
  },
  render: (args) => (
    <TrendLine<TrendLineData>
      {...(args as {
        data: TrendLineData[];
        xKey: keyof TrendLineData;
        yKey: keyof TrendLineData;
        height?: number;
      })}
    />
  ),
};

export const Empty: Story = {
  args: {
    data: [],
    xKey: "month" as never,
    yKey: "value" as never,
  },
  render: (args) => (
    <TrendLine<TrendLineData>
      {...(args as {
        data: TrendLineData[];
        xKey: keyof TrendLineData;
        yKey: keyof TrendLineData;
        height?: number;
      })}
    />
  ),
};