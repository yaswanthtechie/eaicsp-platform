import type { Meta, StoryObj } from "@storybook/react-vite";
import { useForm, FormProvider } from "react-hook-form";
import { Select } from "./Select";

type FormValues = {
  country: string;
};

type SelectStoryArgs = {
  name: "country";
  label: string;
  options: {
    label: string;
    value: string;
  }[];
  placeholder?: string;
  disabled?: boolean;
};

const meta = {
  title: "Forms/Select",
  component: Select,
  tags: ["autodocs"],
} satisfies Meta;

export default meta;

type Story = StoryObj<SelectStoryArgs>;

function SelectStory(args: SelectStoryArgs) {
  const methods = useForm<FormValues>({
    defaultValues: {
      country: "",
    },
  });

  return (
    <FormProvider {...methods}>
      <Select<FormValues> {...args} />
    </FormProvider>
  );
}

const options = [
  { label: "India", value: "india" },
  { label: "United States", value: "usa" },
  { label: "United Kingdom", value: "uk" },
];

export const Default: Story = {
  render: (args) => <SelectStory {...args} />,
  args: {
    name: "country",
    label: "Country",
    options,
  },
};

export const Disabled: Story = {
  render: (args) => <SelectStory {...args} />,
  args: {
    name: "country",
    label: "Country",
    disabled: true,
    options,
  },
};
