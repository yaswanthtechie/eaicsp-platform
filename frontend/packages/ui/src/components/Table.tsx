import React from "react";
import { colors, spacing, radius } from "../theme/tokens";
import { Spinner } from "./Spinner";

export interface Column<T> {
  key: keyof T;
  header: string;
  render?: (row: T) => React.ReactNode;
}

type TableProps<T> = {
  columns: Column<T>[];
  data: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  emptyMessage?: string;
};

export function Table<T>({
  columns,
  data,
  rowKey,
  loading = false,
  emptyMessage = "No data available",
}: TableProps<T>) {
  if (loading) {
    return <Spinner />;
  }

  if (data.length === 0) {
    return <p>{emptyMessage}</p>;
  }

  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
      backgroundColor: colors.white,
color: colors.gray900,
border: `1px solid ${colors.gray200}`,
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
                padding: spacing.md,
                textAlign: "left",
              }}
            >
              {column.header}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {data.map((row) => (
          <tr key={rowKey(row)}>
            {columns.map((column) => (
              <td
                key={String(column.key)}
                style={{
                  border: `1px solid ${colors.border}`,
                  padding: spacing.md,
                }}
              >
                {column.render
                  ? column.render(row)
                  : String(row[column.key] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}