import type { Meta, StoryObj } from "@storybook/react-vite";
import { Card } from "./Card";
import { Button } from "./Button";

const meta = {
  title: "Components/Card",
  component: Card,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  argTypes: {
    title: {
      control: "text",
    },
  },
} satisfies Meta<typeof Card>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: "Card Title",
    children: "This is the default Card component.",
  },
};

export const WithoutTitle: Story = {
  args: {
    children: "This card does not have a title.",
  },
};

export const WithActions: Story = {
  args: {
    title: "Card With Actions",
    actions: <Button size="sm">Action</Button>,
    children: "This card contains an action button.",
  },
};

export const RichContent: Story = {
  args: {
    title: "Dashboard Card",
    children: (
      <div>
        <p>Revenue increased by 12% this month.</p>
        <p>Last updated: Today</p>
      </div>
    ),
  },
};