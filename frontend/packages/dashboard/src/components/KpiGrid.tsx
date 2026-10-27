import { colors, radius, space } from "../tokens";

export interface Kpi {
  title: string;
  value: number;
}

interface KpiGridProps {
  kpis: Kpi[];
  selectedKpi: string;
  lowStockOnly: boolean;
  onSelect: (title: string) => void;
}

function KpiGrid({ kpis, selectedKpi, lowStockOnly, onSelect }: KpiGridProps) {
  return (
    <div>
      <div style={{ marginBottom: space.md }}>
        <h2
          style={{
            color: colors.text,
            marginTop: 0,
            marginBottom: space.sm,
          }}
        >
          Inventory Quick Check
        </h2>

        <p
          style={{
            color: colors.textMuted,
            fontSize: 14,
            margin: 0,
          }}
        >
          Quickly check inventory health, low-stock items, reorder requirements,
          and active alerts. Select a KPI to filter the inventory table.
        </p>
      </div>
      <div className="kpi-grid">
        {kpis.map((kpi) => (
          <button
            key={kpi.title}
            type="button"
            onClick={() => onSelect(kpi.title)}
            aria-pressed={selectedKpi === kpi.title}
            style={{
              background: colors.surface,
              border: `1px solid ${
                selectedKpi === kpi.title
                  ? colors.primary
                  : (kpi.title === "Low Stock" ||
                        kpi.title === "Reorder Items") &&
                      lowStockOnly
                    ? colors.warning
                    : colors.border
              }`,
              borderRadius: radius.md,
              padding: space.lg,
              cursor: "pointer",
              boxSizing: "border-box",
              minWidth: 0,
            }}
          >
            <div
              style={{
                color: colors.textMuted,
                fontSize: 14,
                marginBottom: space.sm,
              }}
            >
              {kpi.title}
            </div>

            <div
              style={{
                color: colors.text,
                fontSize: 28,
                fontWeight: 700,
              }}
            >
              {kpi.value}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default KpiGrid;
