import { useState } from "react";
import type { InventoryItem } from "../../types/forecast";
import {
    exportDashboardCsv,
    type CsvExportView,
} from "../../utils/exportCsv";
import type {
    ShipmentStatus,
    SupplierRiskItem,
} from "../../types/dashboard";
import type { UserRole } from "../../mocks/user";
import { colors, radius, space } from "../../tokens";

interface ExportButtonsProps {
    role: UserRole;
    inventory: InventoryItem[];
    suppliers: SupplierRiskItem[];
    shipments: ShipmentStatus;
}

const VIEW_LABELS: Record<CsvExportView, string> = {
    inventory: "Inventory",
    suppliers: "Suppliers",
    shipments: "Shipments",
};

// Which CSV views each role is allowed to export.
// Must match what the role can SEE on the dashboard.
const VIEWS_BY_ROLE: Record<UserRole, CsvExportView[]> = {
    ceo: ["inventory", "suppliers", "shipments"],
    warehouse_manager: ["inventory", "shipments"],
};

const ExportButtons = ({
    role,
    inventory,
    suppliers,
    shipments,
}: ExportButtonsProps) => {
    const [view, setView] = useState<CsvExportView>("inventory");

    const allowedViews = VIEWS_BY_ROLE[role];

    // If the role changes while a now-forbidden view is selected,
    // fall back to inventory instead of exporting it.
    const activeView: CsvExportView = allowedViews.includes(view)
        ? view
        : "inventory";

    const handleCsvExport = (): void => {
        if (activeView === "inventory") {
            exportDashboardCsv("inventory", inventory);
            return;
        }

        if (activeView === "suppliers") {
            exportDashboardCsv("suppliers", suppliers);
            return;
        }

        exportDashboardCsv("shipments", shipments);
    };

    return (
        <div
            style={{
                display: "flex",
                gap: space.sm,
                alignItems: "center",
                marginBottom: space.sm,
            }}
        >
            <select
                value={activeView}
                onChange={(event) => {
                    setView(event.target.value as CsvExportView);
                }}
                aria-label="CSV export view"
                style={{
                    padding: space.sm,
                    borderRadius: radius.md,
                    border: `1px solid ${colors.border}`,
                    background: colors.surface,
                    color: colors.text,
                    cursor: "pointer",
                    fontSize: space.md,
                }}
            >
                {allowedViews.map((option) => (
                    <option key={option} value={option}>
                        {VIEW_LABELS[option]}
                    </option>
                ))}
            </select>

            <button
                type="button"
                onClick={handleCsvExport}
                style={{
                    padding: space.sm,
                    borderRadius: radius.md,
                    border: `1px solid ${colors.border}`,
                    background: colors.surface,
                    color: colors.text,
                    cursor: "pointer",
                    fontSize: space.md,
                    fontWeight: 600,
                }}
            >
                Export CSV
            </button>
        </div>
    );
};

export default ExportButtons;