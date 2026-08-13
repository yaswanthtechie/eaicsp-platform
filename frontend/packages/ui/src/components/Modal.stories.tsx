import type { Meta, StoryObj } from '@storybook/react';
import { Modal } from './Modal';

const meta = {
  title: 'Components/Modal',
  component: Modal,
} satisfies Meta<typeof Modal>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    isOpen: true,
    title: 'Example Modal',
    children: (
      <p>
        This is an example modal. Use Tab and Shift+Tab to test keyboard
        navigation and Escape to close it.
      </p>
    ),
    onClose: () => {},
  },
};

export const LongContent: Story = {
  args: {
    isOpen: true,
    title: 'Long Content Modal',
    children: (
      <div>
        <p>
          This modal contains longer content to test scrolling and keyboard
          navigation.
        </p>

        <p>
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </p>

        <p>
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </p>

        <p>
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </p>
      </div>
    ),
    onClose: () => {},
  },
};