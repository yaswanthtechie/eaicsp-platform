import React, {
  useCallback,
  useMemo,
  useState,
} from "react";
import "./DataTable.css";
import { TableRow } from "./TableRow";

export interface Column<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  searchable?: boolean;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  pageSize?: number;
  selectableRows?: boolean;
  selectedRows?: T[];
  onSelectionChange?: (rows: T[]) => void;
  rowKey?: (row: T) => React.Key;
}

type SortDirection = "asc" | "desc";

export function DataTable<T>({
  data,
  columns,
  pageSize = 5,
  selectableRows = false,
  selectedRows = [],
  onSelectionChange,
  rowKey,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] =
    useState<keyof T | null>(null);

  const [sortDirection, setSortDirection] =
    useState<SortDirection>("asc");

  const [filters, setFilters] =
    useState<Partial<Record<keyof T, string>>>({});

  const [currentPage, setCurrentPage] =
    useState(1);

  /*
   * Sorting
   */
  const handleSort = (key: keyof T) => {
    if (sortKey === key) {
      setSortDirection((previous) =>
        previous === "asc" ? "desc" : "asc"
      );
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }

    setCurrentPage(1);
  };

  /*
   * Filtering
   */
  const handleFilterChange = (
    key: keyof T,
    value: string
  ) => {
    setFilters((previous) => ({
      ...previous,
      [key]: value,
    }));

    setCurrentPage(1);
  };

  /*
   * Memoized filtering
   */
  const filteredData = useMemo(() => {
    return data.filter((row) => {
      return columns.every((column) => {
        const filterValue = filters[column.key];

        if (!filterValue?.trim()) {
          return true;
        }

        const rowValue = row[column.key];

        return String(rowValue ?? "")
          .toLowerCase()
          .includes(filterValue.toLowerCase());
      });
    });
  }, [data, columns, filters]);

  /*
   * Memoized sorting
   */
  const sortedData = useMemo(() => {
    if (!sortKey) {
      return filteredData;
    }

    return [...filteredData].sort((a, b) => {
      const aValue = a[sortKey];
      const bValue = b[sortKey];

      if (aValue === bValue) {
        return 0;
      }

      if (aValue == null) {
        return 1;
      }

      if (bValue == null) {
        return -1;
      }

      const comparison = String(aValue).localeCompare(
        String(bValue),
        undefined,
        {
          numeric: true,
        }
      );

      return sortDirection === "asc"
        ? comparison
        : -comparison;
    });
  }, [filteredData, sortKey, sortDirection]);

  /*
   * Memoized total pages
   */
  const totalPages = useMemo(() => {
    return Math.ceil(
      sortedData.length / pageSize
    );
  }, [sortedData.length, pageSize]);

  /*
   * Memoized pagination
   */
  const paginatedData = useMemo(() => {
    const startIndex =
      (currentPage - 1) * pageSize;

    return sortedData.slice(
      startIndex,
      startIndex + pageSize
    );
  }, [sortedData, currentPage, pageSize]);

  /*
   * Row selection
   */
  const isSelected = (row: T) => {
    return selectedRows.some(
      (selectedRow) =>
        selectedRow === row
    );
  };

  const handleRowSelection = useCallback(
  (row: T) => {
    if (!onSelectionChange) {
      return;
    }

    const exists = selectedRows.some(
      (selectedRow) => selectedRow === row
    );

    const updatedRows = exists
      ? selectedRows.filter(
          (selectedRow) => selectedRow !== row
        )
      : [...selectedRows, row];

    onSelectionChange(updatedRows);
  },
  [selectedRows, onSelectionChange]
);

  /*
   * Select all rows on current page
   */
  const handleSelectAll = () => {
    if (!onSelectionChange) {
      return;
    }

    const allSelected =
      paginatedData.length > 0 &&
      paginatedData.every((row) =>
        isSelected(row)
      );

    if (allSelected) {
      const remainingRows =
        selectedRows.filter(
          (selectedRow) =>
            !paginatedData.includes(
              selectedRow
            )
        );

      onSelectionChange(remainingRows);
    } else {
      const mergedRows = [...selectedRows];

      paginatedData.forEach((row) => {
        if (!isSelected(row)) {
          mergedRows.push(row);
        }
      });

      onSelectionChange(mergedRows);
    }
  };

  return (
    <div className="datatable">
      <table
        className="datatable-table"
        aria-label="Data table"
      >
        <thead>
          {/* Column headers */}
          <tr>
            {selectableRows && (
              <th scope="col">
                <input
                  type="checkbox"
                  checked={
                    paginatedData.length > 0 &&
                    paginatedData.every((row) =>
                      isSelected(row)
                    )
                  }
                  onChange={handleSelectAll}
                  aria-label="Select all rows on current page"
                />
              </th>
            )}

            {columns.map((column) => {
              const isSorted =
                sortKey === column.key;

              return (
                <th
                  key={String(column.key)}
                  scope="col"
                  aria-sort={
                    isSorted
                      ? sortDirection === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  {column.sortable ? (
                    <button
                      type="button"
                      onClick={() =>
                        handleSort(column.key)
                      }
                      aria-label={`Sort by ${column.label}`}
                    >
                      {column.label}

                      {isSorted &&
                        (sortDirection === "asc"
                          ? " ↑"
                          : " ↓")}
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>

          {/* Search row */}
          <tr>
            {selectableRows && (
              <th
                scope="col"
                aria-hidden="true"
              />
            )}

            {columns.map((column) => (
              <th
                key={String(column.key)}
                scope="col"
              >
                {column.searchable && (
                  <input
                    type="text"
                    placeholder={`Search ${column.label}`}
                    value={
                      filters[column.key] ?? ""
                    }
                    onChange={(event) =>
                      handleFilterChange(
                        column.key,
                        event.target.value
                      )
                    }
                    aria-label={`Search ${column.label}`}
                  />
                )}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {paginatedData.length === 0 ? (
            <tr>
              <td
                colSpan={
                  columns.length +
                  (selectableRows ? 1 : 0)
                }
                className="datatable-empty"
              >
                <span
                  role="status"
                  aria-live="polite"
                >
                  No data available
                </span>
              </td>
            </tr>
          ) : (
            paginatedData.map((row, index) => (
           <TableRow
  key={
    rowKey
      ? rowKey(row)
      : index
  }
  row={row}
  index={index}
  columns={columns}
  selectableRows={selectableRows}
  selected={isSelected(row)}
  onSelectionChange={
    handleRowSelection
  }
/>
            ))
          )}
        </tbody>
      </table>

      {/* Pagination */}
      <nav
        className="datatable-pagination"
        aria-label="Data table pagination"
      >
        <button
          type="button"
          disabled={currentPage === 1}
          onClick={() =>
            setCurrentPage(
              (previous) =>
                previous - 1
            )
          }
          aria-label="Go to previous page"
        >
          Previous
        </button>

        <span aria-live="polite">
          Page {currentPage} of{" "}
          {totalPages || 1}
        </span>

        <button
          type="button"
          disabled={
            currentPage === totalPages ||
            totalPages === 0
          }
          onClick={() =>
            setCurrentPage(
              (previous) =>
                previous + 1
            )
          }
          aria-label="Go to next page"
        >
          Next
        </button>
      </nav>
    </div>
  );
}