
import {
  useController,
  useFormContext,
  type FieldPath,
  type FieldValues,
} from "react-hook-form";

export interface InputProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  placeholder?: string;
  type?: "text" | "email" | "password" | "number";
  disabled?: boolean;
}

export function Input<T extends FieldValues>({
  name,
  label,
  placeholder,
  type = "text",
  disabled = false,
}: InputProps<T>) {
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

      <input
        id={name}
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        {...field}
      />

      {error && (
        <p>
          {error.message}
        </p>
      )}
    </div>
  );
}