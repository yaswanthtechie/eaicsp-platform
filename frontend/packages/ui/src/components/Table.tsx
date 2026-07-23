import React from "react";
import { colors, space, radius } from "../tokens";

export interface Column<T> {
  key: keyof T;
  header: string;
  render?: (row: T) => React.ReactNode;
}

type TableProps<T> = {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  emptyMessage?: string;
};

export function Table<T>({
  columns,
  data,
  loading = false,
  emptyMessage = "No data available",
}: TableProps<T>) {
  if (loading) {
    return <p>Loading...</p>;
  }

  if (data.length === 0) {
    return <p>{emptyMessage}</p>;
  }

  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
        backgroundColor: colors.surface,
        color: colors.text,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
      }}
    >
      <thead>
        <tr>
          {columns.map((column) => (
            <th
              key={String(column.key)}
              style={{
                border: `1px solid ${colors.border}`,
                padding: space.md,
                textAlign: "left",
              }}
            >
              {column.header}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {data.map((row, rowIndex) => (
          <tr key={rowIndex}>
            {columns.map((column) => (
              <td
                key={String(column.key)}
                style={{
                  border: `1px solid ${colors.border}`,
                  padding: space.md,
                }}
              >
                {column.render
                  ? column.render(row)
                  : String(row[column.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}