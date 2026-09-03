import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm, FormProvider } from "react-hook-form";
import { Input } from "./Input";

type FormValues = {
  email: string;
};

type InputStoryArgs = {
  name: "email";
  label: string;
  placeholder?: string;
  type?: "text" | "email" | "password" | "number";
  disabled?: boolean;
};

const meta = {
  title: "Forms/Input",
  component: Input,
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj<InputStoryArgs>;

function InputStory(args: InputStoryArgs) {
  const methods = useForm<FormValues>({
    defaultValues: {
      email: "",
    },
  });

  return (
    <FormProvider {...methods}>
      <Input<FormValues> {...args} />
    </FormProvider>
  );
}

export const Default: Story = {
  render: (args) => <InputStory {...args} />,
  args: {
    name: "email",
    label: "Email",
    placeholder: "Enter your email",
    type: "email",
  },
};

export const Disabled: Story = {
  render: (args) => <InputStory {...args} />,
  args: {
    name: "email",
    label: "Email",
    placeholder: "Enter your email",
    type: "email",
    disabled: true,
  },
};
