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
  selectedRows,
  onSelectionChange,
  rowKey,
}: DataTableProps<T>) {
  /* --------------------------------
     Sorting state
  -------------------------------- */

  const [sortKey, setSortKey] =
    useState<keyof T | null>(null);

  const [sortDirection, setSortDirection] =
    useState<SortDirection>("asc");

  /* --------------------------------
     Filtering state
  -------------------------------- */

  const [filters, setFilters] =
    useState<Partial<Record<keyof T, string>>>({});

  /* --------------------------------
     Pagination state
  -------------------------------- */

  const [currentPage, setCurrentPage] = useState(1);

  /* --------------------------------
     Local selection state

     Used when selectedRows is not
     provided by the parent.
  -------------------------------- */

  const [internalSelectedRows, setInternalSelectedRows] =
    useState<T[]>(selectedRows ?? []);

  /* --------------------------------
     Current selection

     If selectedRows is provided, the
     component is controlled and uses
     the parent's value.

     Otherwise, it uses local state.
  -------------------------------- */

  const currentSelectedRows =
    selectedRows !== undefined
      ? selectedRows
      : internalSelectedRows;

  /* --------------------------------
     Row identity helper
  -------------------------------- */

  const getRowKey = useCallback(
    (row: T): React.Key => {
      if (rowKey) {
        return rowKey(row);
      }

      return row as unknown as React.Key;
    },
    [rowKey]
  );

  /* --------------------------------
     Check whether two rows are the same
  -------------------------------- */

  const areRowsEqual = useCallback(
    (first: T, second: T) => {
      if (rowKey) {
        return getRowKey(first) === getRowKey(second);
      }

      return first === second;
    },
    [getRowKey, rowKey]
  );

  /* --------------------------------
     Sorting
  -------------------------------- */

  const handleSort = useCallback(
    (key: keyof T) => {
      if (sortKey === key) {
        setSortDirection((previous) =>
          previous === "asc" ? "desc" : "asc"
        );
      } else {
        setSortKey(key);
        setSortDirection("asc");
      }

      setCurrentPage(1);
    },
    [sortKey]
  );

  /* --------------------------------
     Filtering
  -------------------------------- */

  const handleFilterChange = useCallback(
    (key: keyof T, value: string) => {
      setFilters((previous) => ({
        ...previous,
        [key]: value,
      }));

      setCurrentPage(1);
    },
    []
  );

  /* --------------------------------
     Filtering calculation
  -------------------------------- */

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

  /* --------------------------------
     Sorting calculation
  -------------------------------- */

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
  }, [
    filteredData,
    sortKey,
    sortDirection,
  ]);

  /* --------------------------------
     Total pages
  -------------------------------- */

  const totalPages = useMemo(() => {
    return Math.ceil(
      sortedData.length / pageSize
    );
  }, [sortedData.length, pageSize]);

  /* --------------------------------
     Pagination
  -------------------------------- */

  const paginatedData = useMemo(() => {
    const startIndex =
      (currentPage - 1) * pageSize;

    return sortedData.slice(
      startIndex,
      startIndex + pageSize
    );
  }, [
    sortedData,
    currentPage,
    pageSize,
  ]);

  /* --------------------------------
     Check if row is selected
  -------------------------------- */

  const isSelected = useCallback(
    (row: T) => {
      return currentSelectedRows.some(
        (selectedRow) =>
          areRowsEqual(selectedRow, row)
      );
    },
    [
      currentSelectedRows,
      areRowsEqual,
    ]
  );

  /* --------------------------------
     Update selection
  -------------------------------- */

  const updateSelection = useCallback(
    (rows: T[]) => {
      /*
       * Only update local state when
       * the component is uncontrolled.
       */
      if (selectedRows === undefined) {
        setInternalSelectedRows(rows);
      }

      /*
       * Notify parent if callback exists.
       */
      onSelectionChange?.(rows);
    },
    [selectedRows, onSelectionChange]
  );

  /* --------------------------------
     Individual row selection
  -------------------------------- */

  const handleRowSelection = useCallback(
    (row: T) => {
      const exists = currentSelectedRows.some(
        (selectedRow) =>
          areRowsEqual(selectedRow, row)
      );

      let updatedRows: T[];

      if (exists) {
        updatedRows =
          currentSelectedRows.filter(
            (selectedRow) =>
              !areRowsEqual(
                selectedRow,
                row
              )
          );
      } else {
        updatedRows = [
          ...currentSelectedRows,
          row,
        ];
      }

      updateSelection(updatedRows);
    },
    [
      currentSelectedRows,
      areRowsEqual,
      updateSelection,
    ]
  );

  /* --------------------------------
     Header Select All
     Current page only
  -------------------------------- */

  const handleSelectAll = useCallback(() => {
    if (paginatedData.length === 0) {
      return;
    }

    const allSelected = paginatedData.every(
      (row) => isSelected(row)
    );

    if (allSelected) {
      /*
       * Remove all current-page rows
       * from selection.
       */
      const remainingRows =
        currentSelectedRows.filter(
          (selectedRow) =>
            !paginatedData.some(
              (row) =>
                areRowsEqual(
                  selectedRow,
                  row
                )
            )
        );

      updateSelection(remainingRows);
    } else {
      /*
       * Add all current-page rows.
       */
      const mergedRows = [
        ...currentSelectedRows,
      ];

      paginatedData.forEach((row) => {
        const alreadySelected =
          mergedRows.some(
            (selectedRow) =>
              areRowsEqual(
                selectedRow,
                row
              )
          );

        if (!alreadySelected) {
          mergedRows.push(row);
        }
      });

      updateSelection(mergedRows);
    }
  }, [
    paginatedData,
    isSelected,
    currentSelectedRows,
    areRowsEqual,
    updateSelection,
  ]);

  /* --------------------------------
     Header checkbox state
  -------------------------------- */

  const allCurrentPageSelected =
    paginatedData.length > 0 &&
    paginatedData.every((row) =>
      isSelected(row)
    );

  const someCurrentPageSelected =
    paginatedData.some((row) =>
      isSelected(row)
    );

  /* --------------------------------
     Render
  -------------------------------- */

  return (
    <div className="datatable">
      <table
        className="datatable-table"
        aria-label="Data table"
      >
        <thead>
          {/* =========================
              HEADER ROW
          ========================= */}

          <tr>
            {selectableRows && (
              <th scope="col">
                <input
                  type="checkbox"
                  checked={allCurrentPageSelected}
                  ref={(checkbox) => {
                    if (checkbox) {
                      checkbox.indeterminate =
                        someCurrentPageSelected &&
                        !allCurrentPageSelected;
                    }
                  }}
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
                        handleSort(
                          column.key
                        )
                      }
                      aria-label={`Sort by ${column.label}`}
                    >
                      {column.label}

                      {isSorted &&
                        (sortDirection ===
                        "asc"
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

          {/* =========================
              SEARCH ROW
          ========================= */}

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
                      filters[
                        column.key
                      ] ?? ""
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

        {/* =========================
            TABLE BODY
        ========================= */}

        <tbody>
          {paginatedData.length === 0 ? (
            <tr>
              <td
                colSpan={
                  columns.length +
                  (selectableRows
                    ? 1
                    : 0)
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
            paginatedData.map(
              (row, index) => (
                <TableRow
                  key={
                    rowKey
                      ? rowKey(row)
                      : index
                  }
                  row={row}
                  index={index}
                  columns={columns}
                  selectableRows={
                    selectableRows
                  }
                  selected={isSelected(row)}
                  onSelectionChange={
                    handleRowSelection
                  }
                />
              )
            )
          )}
        </tbody>
      </table>

      {/* =========================
          PAGINATION
      ========================= */}

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
            currentPage ===
              totalPages ||
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