import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";

import {
    generateInventoryInsight,
    generateWarehouseInsight,
    generateSupplierInsight,
    generateShipmentInsight
} from "../utils/insights";

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
        <Card className="w-full">
            <CardHeader>
                <CardTitle>Dashboard Insights</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                    {generateInventoryInsight(inventory)}
                </p>

                <p className="text-sm text-muted-foreground">
                    {generateWarehouseInsight(inventory)}
                </p>

                {showSupplierInsight && (
                    <p className="text-sm text-muted-foreground">
                        {generateSupplierInsight(suppliers)}
                    </p>
                )}

                <p className="text-sm text-muted-foreground">
                    {generateShipmentInsight(shipments)}
                </p>
            </CardContent>
        </Card>
    );
}