import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm, FormProvider } from "react-hook-form";
import { TextArea } from "./Textarea";

type FormValues = {
  message: string;
};

type TextareaStoryArgs = {
  name: "message";
  label: string;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
};

const meta = {
  title: "Forms/Textarea",
  component: TextArea,
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj<TextareaStoryArgs>;

function TextareaStory(args: TextareaStoryArgs) {
  const methods = useForm<FormValues>({
    defaultValues: {
      message: "",
    },
  });

  return (
    <FormProvider {...methods}>
      <TextArea<FormValues> {...args} />
    </FormProvider>
  );
}

export const Default: Story = {
  render: (args) => <TextareaStory {...args} />,
  args: {
    name: "message",
    label: "Message",
    placeholder: "Enter your message",
    rows: 4,
  },
};

export const Disabled: Story = {
  render: (args) => <TextareaStory {...args} />,
  args: {
    name: "message",
    label: "Message",
    placeholder: "Enter your message",
    rows: 4,
    disabled: true,
  },
};
