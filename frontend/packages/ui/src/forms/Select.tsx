import {
  useController,
  useFormContext,
  type FieldPath,
  type FieldValues,
} from "react-hook-form";

export interface SelectOption {
  label: string;
  value: string;
}

export interface SelectProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
}

export function Select<T extends FieldValues>({
  name,
  label,
  options,
  placeholder = "Select an option",
  disabled = false,
}: SelectProps<T>) {
  const { control } = useFormContext<T>();

  const {
    field,
    fieldState: { error },
  } = useController({
    name,
    control,
  });

  return (
    <div>
      <label htmlFor={name}>
        {label}
      </label>

      <select
        id={name}
        {...field}
        disabled={disabled}
      >
        <option value="">
          {placeholder}
        </option>

        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
          >
            {option.label}
          </option>
        ))}
      </select>

      {error && (
        <p>
          {error.message}
        </p>
      )}
    </div>
  );
}