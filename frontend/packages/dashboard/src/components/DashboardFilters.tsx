import { useEffect, useMemo, useState } from "react";
import { loadInventory } from "../mocks/inventory";
import { colors, radius, space } from "../tokens";

interface DashboardFiltersProps {
  onFilterChange: (filters: {
    warehouse: string;
    category: string;
    startDate: string;
    endDate: string;
  }) => void;
}

function DashboardFilters({
  onFilterChange,
}: DashboardFiltersProps) {
  const params = new URLSearchParams(
    window.location.search,
  );

  const [warehouse, setWarehouse] = useState(
    params.get("warehouse") || "All",
  );

  const [category, setCategory] = useState(
    params.get("category") || "All",
  );

  const [startDate, setStartDate] = useState(
    params.get("startDate") || "",
  );

  const [endDate, setEndDate] = useState(
    params.get("endDate") || "",
  );

  const [inventoryData, setInventoryData] = useState<
    Awaited<ReturnType<typeof loadInventory>>
  >([]);

  useEffect(() => {
    let cancelled = false;

    const fetchInventory = async () => {
      try {
        const data = await loadInventory();

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

  useEffect(() => {
    onFilterChange({
      warehouse,
      category,
      startDate,
      endDate,
    });
  }, [
    warehouse,
    category,
    startDate,
    endDate,
    onFilterChange,
  ]);

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
        value={warehouse}
        onChange={(event) => {
          const value = event.target.value;
          setWarehouse(value);
          updateUrl("warehouse", value);
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
        value={category}
        onChange={(event) => {
          const value = event.target.value;
          setCategory(value);
          updateUrl("category", value);
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
        value={startDate}
        onChange={(event) => {
          const value = event.target.value;
          setStartDate(value);
          updateUrl("startDate", value);
        }}
        style={selectStyle}
        aria-label="Start date"
      />

      <input
        type="date"
        value={endDate}
        onChange={(event) => {
          const value = event.target.value;
          setEndDate(value);
          updateUrl("endDate", value);
        }}
        style={selectStyle}
        aria-label="End date"
      />
    </div>
  );
}

export default DashboardFilters;