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
  render: (args) => {
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
        />
      </>
    );
  },
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
  render: (args) => {
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
          footer={
            <>
              <Button
                variant="secondary"
                onClick={() => setIsOpen(false)}
              >
                Cancel
              </Button>

              <Button
                onClick={() => setIsOpen(false)}
              >
                Confirm
              </Button>
            </>
          }
        />
      </>
    );
  },
};