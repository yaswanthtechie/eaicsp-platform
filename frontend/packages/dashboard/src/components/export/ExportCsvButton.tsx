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
import { colors, radius, space } from "../../tokens";

interface ExportButtonsProps {
    inventory: InventoryItem[];
    suppliers: SupplierRiskItem[];
    shipments: ShipmentStatus;
}

const ExportButtons = ({
    inventory,
    suppliers,
    shipments,
}: ExportButtonsProps) => {
    const [view, setView] = useState<CsvExportView>("inventory");

    const handleCsvExport = (): void => {
        if (view === "inventory") {
            exportDashboardCsv("inventory", inventory);
            return;
        }

        if (view === "suppliers") {
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
                value={view}
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
                <option value="inventory">Inventory</option>
                <option value="suppliers">Suppliers</option>
                <option value="shipments">Shipments</option>
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
