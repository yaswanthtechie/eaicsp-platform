import { useEffect, useMemo, useState } from "react";
import { dashboardApi } from "../api/dashboard";
import { colors, radius, space } from "../tokens";

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
}

function DashboardFilters({
  filters,
  onFilterChange,
}: DashboardFiltersProps) {

  const [inventoryData, setInventoryData] = useState<
    Awaited<ReturnType<typeof dashboardApi.fetchInventory>>
  >([]);

  useEffect(() => {
    let cancelled = false;

    const fetchInventory = async () => {
      try {
        const data = await dashboardApi.fetchInventory();

        if (!cancelled) {
          setInventoryData(data);
        }
      } catch {
        if (!cancelled) {
          setInventoryData([]);
        }
      }
    };

    fetchInventory();

    return () => {
      cancelled = true;
    };
  }, []);

  const warehouses = useMemo(
    () =>
      Array.from(
        new Set(
          inventoryData.map(
            (item) => item.warehouse_id,
          ),
        ),
      ),
    [inventoryData],
  );

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          inventoryData.map(
            (item) => item.category,
          ),
        ),
      ),
    [inventoryData],
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

  const selectStyle = {
    background: colors.bg,
    color: colors.text,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    padding: `${space.sm}px ${space.md}px`,
    minWidth: 150,
    boxSizing: "border-box" as const,
  };

  return (
    <div
      style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: space.md,
        marginBottom: space.lg,
        display: "flex",
        gap: space.md,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      <select
        value={filters.warehouse}
        onChange={(event) => {
          const value = event.target.value;

          updateUrl("warehouse", value);

          onFilterChange({
            ...filters,
            warehouse: value,
          });
        }}
        style={selectStyle}
        aria-label="Warehouse filter"
      >
        <option value="All">All Warehouses</option>

        {warehouses.map((warehouseId) => (
          <option
            key={warehouseId}
            value={warehouseId}
          >
            {warehouseId}
          </option>
        ))}
      </select>

      <select
        value={filters.category}
        onChange={(event) => {
          const value = event.target.value;
          
          updateUrl("category", value);

          onFilterChange({
            ...filters,
            category: value,
          });
        }}
        style={selectStyle}
        aria-label="Category filter"
      >
        <option value="All">All Categories</option>

        {categories.map((categoryName) => (
          <option
            key={categoryName}
            value={categoryName}
          >
            {categoryName}
          </option>
        ))}
      </select>

      <input
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
        style={selectStyle}
        aria-label="Start date"
      />

      <input
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
        style={selectStyle}
        aria-label="End date"
      />
    </div>
  );
}

export default DashboardFilters;