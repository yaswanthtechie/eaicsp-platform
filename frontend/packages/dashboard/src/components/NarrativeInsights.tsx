import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";

import {
    generateInventoryInsight,
    generateWarehouseInsight,
    generateSupplierInsight,
    generateShipmentInsight
} from "../utils/insights";

import { colors, radius, space } from "../tokens";
interface NarrativeInsightsProps {
    inventory: InventoryItem[];
    suppliers: SupplierRiskItem[];
    shipments: ShipmentStatus;
    showSupplierInsight: boolean;
}

export default function NarrativeInsights({
    inventory,
    suppliers,
    shipments,
    showSupplierInsight,
}: NarrativeInsightsProps) {
    return (
        <section
            style={{
                padding: space.lg,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
            }}
        >
            <h2 style={{ color: colors.text, marginTop: 0 }}>
                Dashboard Insights
            </h2>

            
            <p style={{ color: colors.warning }}>
                {generateInventoryInsight(inventory)}
            </p>

            <p style={{ color: colors.primary }}>
                {generateWarehouseInsight(inventory)}
            </p>

            {showSupplierInsight && (
                <p style={{ color: colors.danger }}>
                    {generateSupplierInsight(suppliers)}
                </p>
            )}

            <p style={{ color: colors.success }}>
                {generateShipmentInsight(shipments)}
            </p>
        </section>
    );
}