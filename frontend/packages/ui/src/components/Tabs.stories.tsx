import type { Meta, StoryObj } from '@storybook/react';
import { Tabs } from './Tabs';

const meta = {
  title: 'Components/Tabs',
  component: Tabs,
} satisfies Meta<typeof Tabs>;

export default meta;

type Story = StoryObj<typeof meta>;

const tabs = [
  {
    value: 'overview',
    label: 'Overview',
    content: <p>Overview content</p>,
  },
  {
    value: 'details',
    label: 'Details',
    content: <p>Details content</p>,
  },
  {
    value: 'settings',
    label: 'Settings',
    content: <p>Settings content</p>,
  },
];

export const Default: Story = {
  args: {
    items: tabs,
  },
};

export const WithDisabledTab: Story = {
  args: {
    items: [
      {
        value: 'overview',
        label: 'Overview',
        content: <p>Overview content</p>,
      },
      {
        value: 'details',
        label: 'Details',
        content: <p>Details content</p>,
        disabled: true,
      },
      {
        value: 'settings',
        label: 'Settings',
        content: <p>Settings content</p>,
      },
    ],
  },
};

export const Controlled: Story = {
  args: {
    items: tabs,
    value: 'details',
  },
};