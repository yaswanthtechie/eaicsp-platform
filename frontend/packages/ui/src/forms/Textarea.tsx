import {
  useController,
  useFormContext,
  type FieldPath,
  type FieldValues,
} from "react-hook-form";

export interface TextAreaProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}

export function TextArea<T extends FieldValues>({
  name,
  label,
  placeholder,
  rows = 4,
  disabled = false,
}: TextAreaProps<T>) {
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

      <textarea
        id={name}
        rows={rows}
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