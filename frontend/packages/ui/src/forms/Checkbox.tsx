import {
  useController,
  useFormContext,
  type FieldPath,
  type FieldValues,
} from "react-hook-form";

export interface CheckboxProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  disabled?: boolean;
}

export function Checkbox<T extends FieldValues>({
  name,
  label,
  disabled = false,
}: CheckboxProps<T>) {
  const { control } = useFormContext<T>();

  const {
    field,
    fieldState: { error },
  } = useController({
    name,
    control,
    defaultValue: false as T[FieldPath<T>],
  });

  return (
    <div style={{ marginBottom: "1rem" }}>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={Boolean(field.value)}
          onChange={(e) => field.onChange(e.target.checked)}
          onBlur={field.onBlur}
          ref={field.ref}
          disabled={disabled}
        />
        {label}
      </label>

      {error && (
        <p
          style={{
            color: "red",
            marginTop: "4px",
            fontSize: "14px",
          }}
        >
          {error.message}
        </p>
      )}
    </div>
  );
}