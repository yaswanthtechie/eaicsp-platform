import {
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
  const {
    register,
    formState: { errors },
  } = useFormContext<T>();

  const registration = register(name);

  const error = errors[name];

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
          {...registration}
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
          {typeof error.message === "string"
            ? error.message
            : ""}
        </p>
      )}
    </div>
  );
}