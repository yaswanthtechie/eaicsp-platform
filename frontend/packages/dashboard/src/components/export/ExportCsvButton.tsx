import type { InventoryItem } from "../../types/forecast";
import { exportInventoryCsv } from "../../utils/exportCsv";
import { colors, radius, space } from "../../tokens";

interface ExportButtonsProps {
    inventory: InventoryItem[];
}

const ExportButtons = ({
    inventory
}: ExportButtonsProps) => {
    const handleCsvExport = (): void => {
        exportInventoryCsv(inventory);
    };

    return (
        <button
            type="button"
            onClick={handleCsvExport}
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
            Export CSV
        </button>
    );
};

export default ExportButtons;
