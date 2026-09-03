import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm } from "react-hook-form";
import { FormProvider } from "react-hook-form";
import { Checkbox } from "./Checkbox";

type FormValues = {
  terms: boolean;
};

const meta = {
  title: "Forms/Checkbox",
  component: Checkbox,
  tags: ["autodocs"],
} satisfies Meta<typeof Checkbox>;

export default meta;

type Story = StoryObj<typeof meta>;

function CheckboxStory(
  args: React.ComponentProps<typeof Checkbox<FormValues>>,
) {
  const methods = useForm<FormValues>({
    defaultValues: {
      terms: false,
    },
  });

  return (
    <FormProvider {...methods}>
      <Checkbox {...args} />
    </FormProvider>
  );
}

export const Default: Story = {
  args: {
    name: "terms",
    label: "I agree to the terms and conditions",
  },
  render: () => (
    <CheckboxStory
      name="terms"
      label="I agree to the terms and conditions"
    />
  ),
};

export const Disabled: Story = {
  args: {
    name: "terms",
    label: "I agree to the terms and conditions",
    disabled: true,
  },
  render: () => (
    <CheckboxStory
      name="terms"
      label="I agree to the terms and conditions"
      disabled
    />
  ),
};