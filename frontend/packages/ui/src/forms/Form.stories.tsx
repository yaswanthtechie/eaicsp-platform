import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm } from "react-hook-form";
import { Form } from "./Form";
import { Input } from "./Input";

type FormValues = {
  name: string;
};

const meta = {
  title: "Forms/Form",
  component: Form,
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj;

function FormStory() {
  const methods = useForm<FormValues>({
    defaultValues: {
      name: "",
    },
  });

  const onSubmit = () => {};

  return (
    <Form<FormValues> methods={methods} onSubmit={onSubmit}>
      <Input<FormValues>
        name="name"
        label="Name"
        placeholder="Enter your name"
      />

      <button type="submit">
        Submit
      </button>
    </Form>
  );
}

export const Default: Story = {
  render: () => <FormStory />,
};
