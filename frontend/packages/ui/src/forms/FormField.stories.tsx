import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm } from "react-hook-form";
import { FormField } from "./FormField";

type FormValues = {
  username: string;
};

const meta = {
  title: "Forms/FormField",
  component: FormField,
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj;

function FormFieldStory() {
  const methods = useForm<FormValues>({
    defaultValues: {
      username: "",
    },
  });

  return (
    <FormField
      control={methods.control}
      name="username"
      render={({ field }) => (
        <div>
          <label htmlFor="username">
            Username
          </label>

          <input
            id="username"
            {...field}
            placeholder="Enter username"
          />
        </div>
      )}
    />
  );
}

export const Default: Story = {
  render: () => <FormFieldStory />,
};
