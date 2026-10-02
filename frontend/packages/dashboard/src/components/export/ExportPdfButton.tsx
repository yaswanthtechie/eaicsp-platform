import { Button } from "@/components/ui/button";
import { useState } from "react";
import type { InventoryItem } from "../../types/forecast";
import type {
    SupplierRiskItem,
    ShipmentStatus,
} from "../../types/dashboard";
import type { UserRole } from "../../mocks/user";
import { exportDashboardPdf } from "../../utils/exportPdf";
import { colors} from "../../tokens";

interface ExportPdfButtonProps {
    role: UserRole;
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
    kpis,
}: ExportPdfButtonProps) => {
    const [exporting, setExporting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handlePdfExport = async (): Promise<void> => {
        setExporting(true);
        setError(null);

        try {
            await exportDashboardPdf({
                role,
                inventory,
                suppliers,
                shipments,
                filters,
                kpis,
            });
        } catch {
            setError("PDF export failed. Please try again.");
        } finally {
            setExporting(false);
        }
    };

    return (
        <div>
            <Button
                type="button"
                variant="outline"
                size="lg" 
                onClick={handlePdfExport}
                disabled={exporting}
                aria-busy={exporting}
            >
                {exporting ? "Exporting..." : "Export PDF"}
            </Button>

            {error && (
                <p role="alert" style={{ color: colors.danger, margin: 0 }}>
                    {error}
                </p>
            )}
        </div>
    );
};

export default ExportPdfButton;