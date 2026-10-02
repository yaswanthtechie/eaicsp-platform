import {Card, CardContent} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMemo } from "react";
import type { InventoryItem } from "../types/forecast";

interface DashboardFiltersProps {
  filters: {
    warehouse: string;
    category: string;
    startDate: string;
    endDate: string;
  };
  onFilterChange: (filters: {
    warehouse: string;
    category: string;
    startDate: string;
    endDate: string;
  }) => void;
  lockedWarehouse?: string;
  inventory: InventoryItem[];
}

function DashboardFilters({
  filters,
  onFilterChange,
  lockedWarehouse,
  inventory,
}: DashboardFiltersProps) {

  const warehouses = useMemo(
    () =>
      Array.from(
        new Set(
          inventory.map(
            (item) => item.warehouse_id,
          ),
        ),
      ),
    [inventory],
  );

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          inventory.map(
            (item) => item.category,
          ),
        ),
      ),
    [inventory],
  );

  const updateUrl = (
    key: string,
    value: string,
  ) => {
    const newParams = new URLSearchParams(
      window.location.search,
    );

    if (value === "All" || value === "") {
      newParams.delete(key);
    } else {
      newParams.set(key, value);
    }

    const queryString = newParams.toString();

    window.history.pushState(
      {},
      "",
      queryString
        ? `${window.location.pathname}?${queryString}`
        : window.location.pathname,
    );
  };

 return (
  <Card className="mb-6">
    <CardContent className="flex flex-wrap items-center gap-4 p-4">
      <Select
        value={lockedWarehouse ?? filters.warehouse}
        disabled={lockedWarehouse !== undefined}
        onValueChange={(value) => {
          if (value === null ) return;
          updateUrl("warehouse", value);

          onFilterChange({
            ...filters,
            warehouse: value,
          });
        }}
      >
        <SelectTrigger
          className="w-[180px]"
          aria-label="Warehouse filter"
        >
          <SelectValue placeholder="All Warehouses" />
        </SelectTrigger>

        <SelectContent>
          <SelectItem value="All">
            All Warehouses
          </SelectItem>

          {warehouses.map((warehouseId) => (
            <SelectItem
              key={warehouseId}
              value={warehouseId}
            >
              {warehouseId}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.category}
        onValueChange={(value) => {
          if (value === null) return;
          updateUrl("category", value);

          onFilterChange({
            ...filters,
            category: value,
          });
        }}
      >
        <SelectTrigger
          className="w-[180px]"
          aria-label="Category filter"
        >
          <SelectValue placeholder="All Categories" />
        </SelectTrigger>

        <SelectContent>
          <SelectItem value="All">
            All Categories
          </SelectItem>

          {categories.map((categoryName) => (
            <SelectItem
              key={categoryName}
              value={categoryName}
            >
              {categoryName}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Input
        type="date"
        value={filters.startDate}
        onChange={(event) => {
          const value = event.target.value;

          updateUrl("startDate", value);

          onFilterChange({
            ...filters,
            startDate: value,
          });
        }}
        className="w-[180px]"
        aria-label="Start date"
      />

      <Input
        type="date"
        value={filters.endDate}
        onChange={(event) => {
          const value = event.target.value;

          updateUrl("endDate", value);

          onFilterChange({
            ...filters,
            endDate: value,
          });
        }}
        className="w-[180px]"
        aria-label="End date"
      />
    </CardContent>
  </Card>
  );
}

export default DashboardFilters;