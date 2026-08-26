import type { Meta, StoryObj } from "@storybook/react";
import { Tabs } from "./Tabs";

const meta = {
  title: "Components/Tabs",
  component: Tabs,
  tags: ["autodocs"],
} satisfies Meta<typeof Tabs>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    items: [
      {
        value: "overview",
        label: "Overview",
        content: <div>Overview content</div>,
      },
      {
        value: "details",
        label: "Details",
        content: <div>Details content</div>,
      },
      {
        value: "settings",
        label: "Settings",
        content: <div>Settings content</div>,
      },
    ],
  },
};

export const WithDisabledTab: Story = {
  args: {
    items: [
      {
        value: "active",
        label: "Active",
        content: <div>Active content</div>,
      },
      {
        value: "disabled",
        label: "Disabled",
        content: <div>Disabled content</div>,
        disabled: true,
      },
      {
        value: "other",
        label: "Other",
        content: <div>Other content</div>,
      },
    ],
  },
};
