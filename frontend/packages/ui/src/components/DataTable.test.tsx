import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataTable, type Column } from "./DataTable";

type Product = {
  name: string;
  stock: number;
};

const columns: Column<Product>[] = [
  {
    key: "name",
    label: "Name",
    sortable: true,
    searchable: true,
  },
  {
    key: "stock",
    label: "Stock",
    sortable: true,
  },
];

describe("DataTable", () => {
  it("renders empty state", () => {
    render(
      <DataTable
        data={[]}
        columns={columns}
      />
    );

    expect(
      screen.getByText("No data available")
    ).toBeInTheDocument();
  });

  it("renders one page when data is less than page size", () => {
    render(
      <DataTable
        data={[
          { name: "Steel", stock: 10 },
          { name: "Cement", stock: 5 },
        ]}
        columns={columns}
        pageSize={5}
      />
    );

    expect(
      screen.getByText("Page 1 of 1")
    ).toBeInTheDocument();
  });

  it("sorts data when header is clicked", () => {
    render(
      <DataTable
        data={[
          { name: "Zinc", stock: 5 },
          { name: "Aluminium", stock: 10 },
        ]}
        columns={columns}
      />
    );

    fireEvent.click(screen.getByText("Name"));

    expect(
      screen.getByText("Aluminium")
    ).toBeInTheDocument();
  });

  it("filters data correctly", () => {
    render(
      <DataTable
        data={[
          { name: "Steel", stock: 10 },
          { name: "Cement", stock: 5 },
        ]}
        columns={columns}
      />
    );

    fireEvent.change(
      screen.getByPlaceholderText("Search Name"),
      {
        target: {
          value: "Steel",
        },
      }
    );

    expect(
      screen.getByText("Steel")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Cement")
    ).toBeNull();
  });
});