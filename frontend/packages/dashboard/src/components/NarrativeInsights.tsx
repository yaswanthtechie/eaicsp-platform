import { useEffect, useState } from "react";
import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";

import {
    generateInventoryInsight,
    generateWarehouseInsight,
    generateSupplierInsight,
    generateShipmentInsight
} from "../utils/insights";

import { colors, space } from "../tokens";
import Skeleton from "./Skeleton";

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
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setLoading(false);
        }, 1000);

        return () => clearTimeout(timer);
    }, []);

    return (
        <section
            style={{
                padding: space.lg,
                border: `1px solid ${colors.border}`,
                borderRadius: 10,
            }}
        >
            <h2 style={{ color: colors.text, marginTop: 0 }}>
                Dashboard Insights
            </h2>

            {loading ? (
                <div style={{ display: "grid", gap: space.md }}>
                    <Skeleton width="45%" height={20} />
                    <Skeleton width="50%" height={20} />
                    <Skeleton width="48%" height={20} />
                    <Skeleton width="40%" height={20} />
                </div>
            ) : (
                <>
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
                </>
            )}
        </section>
    );
}