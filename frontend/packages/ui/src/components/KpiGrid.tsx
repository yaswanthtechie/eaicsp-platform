import { KpiCard } from "./KpiCard";

export interface KpiItem {
  label: string;
  value: string | number;
  delta?: number;
}

export interface KpiGridProps {
  items: KpiItem[];
  columns?: number;
}

export function KpiGrid({
  items,
  columns = 4,
}: KpiGridProps) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: "24px",
          textAlign: "center",
        }}
      >
        No KPI data available.
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${columns}, minmax(220px, 1fr))`,
        gap: "16px",
        width: "100%",
      }}
    >
      {items.map((item) => (
        <KpiCard
          key={item.label}
          label={item.label}
          value={item.value}
          delta={item.delta}
        />
      ))}
    </div>
  );
}