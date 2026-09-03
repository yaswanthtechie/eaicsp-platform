import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Modal } from "./Modal";
import { Button } from "../Button";

const meta = {
  title: "Components/Modal",
  component: Modal,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
  },
} satisfies Meta<typeof Modal>;

export default meta;

type Story = StoryObj<typeof meta>;

function ModalWithState({
  args,
  footer,
}: {
  args: React.ComponentProps<typeof Modal>;
  footer?: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(args.isOpen);

  return (
    <>
      <Button onClick={() => setIsOpen(true)}>
        Open Modal
      </Button>

      <Modal
        {...args}
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        footer={footer}
      />
    </>
  );
}

export const Default: Story = {
  args: {
    isOpen: true,
    title: "Example Modal",
    onClose: () => {},
    children: (
      <p>
        This modal demonstrates the component in Storybook.
      </p>
    ),
  },
  render: (args) => <ModalWithState args={args} />,
};

export const WithFooter: Story = {
  args: {
    isOpen: true,
    title: "Confirm Action",
    onClose: () => {},
    children: (
      <p>
        Are you sure you want to continue?
      </p>
    ),
  },
  render: (args) => (
    <ModalWithState
      args={args}
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => {}}
          >
            Cancel
          </Button>

          <Button onClick={() => {}}>
            Confirm
          </Button>
        </>
      }
    />
  ),
};