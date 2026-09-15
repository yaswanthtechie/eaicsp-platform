import React from "react";
import type { Column } from "./DataTable";

export interface TableRowProps<T> {
  row: T;
  index: number;
  columns: Column<T>[];
  selectableRows: boolean;
  selected: boolean;
  onSelectionChange: (row: T) => void;
}

function TableRowComponent<T>({
  row,
  index,
  columns,
  selectableRows,
  selected,
  onSelectionChange,
}: TableRowProps<T>) {
  return (
    <tr>
      {selectableRows && (
        <td>
          <input
            type="checkbox"
            checked={selected}
            onChange={() =>
              onSelectionChange(row)
            }
            aria-label={`Select row ${index + 1}`}
          />
        </td>
      )}

      {columns.map((column) => (
        <td key={String(column.key)}>
          {String(row[column.key])}
        </td>
      ))}
    </tr>
  );
}

export const TableRow = React.memo(
  TableRowComponent
) as typeof TableRowComponent;