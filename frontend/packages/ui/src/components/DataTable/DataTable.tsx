import React, { useState } from "react";
import "./DataTable.css";


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

  // Add this
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



  const handleSort = (
    key: keyof T
  ) => {

    if (sortKey === key) {

      setSortDirection(
        sortDirection === "asc"
          ? "desc"
          : "asc"
      );

    } else {

      setSortKey(key);
      setSortDirection("asc");

    }

    setCurrentPage(1);
  };



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



  const filteredData = data.filter(
    (row) => {

      return columns.every(
        (column) => {

          const filterValue =
            filters[column.key];


          if (
            !column.searchable ||
            !filterValue
          ) {
            return true;
          }


          return String(row[column.key])
            .toLowerCase()
            .includes(
              filterValue.toLowerCase()
            );

        }
      );

    }
  );



  const sortedData = [...filteredData].sort(
    (a, b) => {

      if (!sortKey) {
        return 0;
      }


      const valueA = a[sortKey];
      const valueB = b[sortKey];


      if (valueA === valueB) {
        return 0;
      }


      if (
        valueA === null ||
        valueA === undefined
      ) {
        return 1;
      }


      if (
        valueB === null ||
        valueB === undefined
      ) {
        return -1;
      }


      let result = 0;


      if (
        typeof valueA === "number" &&
        typeof valueB === "number"
      ) {

        result = valueA - valueB;

      } else {

        result = String(valueA)
          .localeCompare(
            String(valueB)
          );

      }


      return sortDirection === "asc"
        ? result
        : -result;

    }
  );



  const totalPages = Math.ceil(
    sortedData.length / pageSize
  );



  const paginatedData =
    sortedData.slice(
      (currentPage - 1) * pageSize,
      currentPage * pageSize
    );



  const isSelected = (
    row: T
  ) => {

    return selectedRows.some(
      (selectedRow) =>
        selectedRow === row
    );

  };



  const handleRowSelection = (
    row: T
  ) => {

    if (!onSelectionChange) {
      return;
    }


    const exists = isSelected(row);


    const updatedRows = exists

      ? selectedRows.filter(
          (selectedRow) =>
            selectedRow !== row
        )

      : [
          ...selectedRows,
          row
        ];


    onSelectionChange(updatedRows);

  };



  const handleSelectAll = () => {

    if (!onSelectionChange) {
      return;
    }


    const allSelected =
      paginatedData.every(
        (row) => isSelected(row)
      );


    if (allSelected) {

      const remainingRows =
        selectedRows.filter(
          (selectedRow) =>
            !paginatedData.includes(
              selectedRow
            )
        );


      onSelectionChange(
        remainingRows
      );

    } else {

      const mergedRows = [
        ...selectedRows
      ];


      paginatedData.forEach(
        (row) => {

          if (!isSelected(row)) {
            mergedRows.push(row);
          }

        }
      );


      onSelectionChange(
        mergedRows
      );

    }

  };



  return (

    <div className="datatable">


      {paginatedData.length === 0 ? (

        <div className="datatable-empty">
          No data available
        </div>

      ) : (

        <table className="datatable-table">


          <thead>

            <tr>


              {
                selectableRows && (

                  <th>

                    <input
                      type="checkbox"
                      checked={
                        paginatedData.length > 0 &&
                        paginatedData.every(
                          (row) =>
                            isSelected(row)
                        )
                      }
                      onChange={
                        handleSelectAll
                      }
                    />

                  </th>

                )
              }



              {
                columns.map(
                  (column) => (

                    <th
                      key={
                        String(column.key)
                      }
                      onClick={() =>
                        column.sortable &&
                        handleSort(
                          column.key
                        )
                      }
                    >

                      {column.label}


                      {
                        sortKey === column.key &&
                        (
                          sortDirection === "asc"
                            ? " ↑"
                            : " ↓"
                        )
                      }


                    </th>

                  )
                )
              }


            </tr>



            <tr>


              {
                selectableRows && (
                  <th />
                )
              }



              {
                columns.map(
                  (column) => (

                    <th
                      key={
                        String(column.key)
                      }
                    >

                      {
                        column.searchable && (

                          <input
                            type="text"
                            placeholder={
                              `Search ${column.label}`
                            }
                            value={
                              filters[column.key] ?? ""
                            }
                            onChange={
                              (event) =>
                                handleFilterChange(
                                  column.key,
                                  event.target.value
                                )
                            }
                          />

                        )
                      }

                    </th>

                  )
                )
              }


            </tr>


          </thead>



          <tbody>


            {
              paginatedData.map(
                (row, index) => (

                <tr key={rowKey ? rowKey(row) : index}>


                    {
                      selectableRows && (

                        <td>

                          <input
                            type="checkbox"
                            checked={
                              isSelected(row)
                            }
                            onChange={() =>
                              handleRowSelection(
                                row
                              )
                            }
                          />

                        </td>

                      )
                    }



                    {
                      columns.map(
                        (column) => (

                          <td
                            key={
                              String(column.key)
                            }
                          >

                            {
                              String(
                                row[column.key]
                              )
                            }

                          </td>

                        )
                      )
                    }


                  </tr>

                )
              )
            }


          </tbody>


        </table>

      )}



      <div className="datatable-pagination">


        <button
          disabled={
            currentPage === 1
          }
          onClick={() =>
            setCurrentPage(
              currentPage - 1
            )
          }
        >
          Previous
        </button>



        <span>
          Page {currentPage} of {totalPages || 1}
        </span>



        <button
          disabled={
            currentPage === totalPages ||
            totalPages === 0
          }
          onClick={() =>
            setCurrentPage(
              currentPage + 1
            )
          }
        >
          Next
        </button>


      </div>


    </div>

  );
}