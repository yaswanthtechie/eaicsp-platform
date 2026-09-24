import type { InventoryItem } from "../../types/forecast";
import type {
    SupplierRiskItem,
    ShipmentStatus
} from "../../types/dashboard";
import { exportDashboardPdf } from "../../utils/exportPdf";
import { colors, radius, space } from "../../tokens";

interface ExportPdfButtonProps {
    role: "ceo" | "warehouse_manager";
    inventory: InventoryItem[];
    suppliers: SupplierRiskItem[];
    shipments: ShipmentStatus;
    filters: {
        warehouse: string;
        category: string;
        startDate: string;
        endDate: string;
    };
    kpis: {
        title: string;
        value: number;
    }[];
}

const ExportPdfButton = ({
    role,
    inventory,
    suppliers,
    shipments,
    filters,
    kpis
}: ExportPdfButtonProps) => {
    const handlePdfExport = async (): Promise<void> => {
        exportDashboardPdf({
            role,
            inventory,
            suppliers,
            shipments,
            filters,
            kpis
        });
    };

    return (
        <button
            type="button"
            onClick={handlePdfExport}
            style={{
                padding: space.sm,
                borderRadius: radius.md,
                marginBottom:space.sm,
                border: `1px solid ${colors.border}`,
                background: colors.surface,
                color: colors.text,
                cursor: "pointer",
                fontSize: space.md,
                fontWeight: 600
            }}
        >
            Export PDF
        </button>
    );
};

export default ExportPdfButton;