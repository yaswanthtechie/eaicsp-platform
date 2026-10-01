import type { InventoryItem } from "../types/forecast";
import type {
    SupplierRiskItem,
    ShipmentStatus,
} from "../types/dashboard";

export type CsvExportView =
    | "inventory"
    | "suppliers"
    | "shipments";

const FORMULA_PREFIX = /^[=+\-@\t\r]/;

const escapeCsvValue = (
    value: string | number | boolean
): string => {
    let stringValue = String(value);

    if (typeof value === "string" && FORMULA_PREFIX.test(value)) {
        stringValue = `'${stringValue}`;
    }

    if (
        stringValue.includes(",") ||
        stringValue.includes('"') ||
        stringValue.includes("\n") ||
        stringValue.includes("\r")
    ) {
        return `"${stringValue.replace(/"/g, '""')}"`;
    }

    return stringValue;
};

const downloadCsv = (
    headers: string[],
    rows: (string | number | boolean)[][],
    filename: string
): void => {
    const csvContent = [
        headers,
        ...rows,
    ]
        .map((row) =>
            row.map(escapeCsvValue).join(",")
        )
        .join("\n");

    const blob = new Blob(
        [csvContent],
        {
            type: "text/csv;charset=utf-8;",
        }
    );

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
};

export function exportDashboardCsv(
    view: "inventory",
    data: InventoryItem[]
): void;

export function exportDashboardCsv(
    view: "suppliers",
    data: SupplierRiskItem[]
): void;

export function exportDashboardCsv(
    view: "shipments",
    data: ShipmentStatus
): void;

export function exportDashboardCsv(
    view: CsvExportView,
    data:
        | InventoryItem[]
        | SupplierRiskItem[]
        | ShipmentStatus
): void {
    if (view === "inventory") {
        const inventory = data as InventoryItem[];

        const headers = [
            "SKU",
            "Product",
            "Category",
            "Warehouse",
            "Quantity On Hand",
            "Reorder Point",
            "Needs Reorder",
            "Average Daily Demand",
        ];

        const rows = inventory.map((item) => [
            item.sku_id,
            item.product_name,
            item.category,
            item.warehouse_id,
            item.quantity_on_hand,
            item.reorder_point,
            item.needs_reorder,
            item.avg_daily_demand,
        ]);

        downloadCsv(
            headers,
            rows,
            "inventory-export.csv"
        );

        return;
    }

    if (view === "suppliers") {
        const suppliers = data as SupplierRiskItem[];

        const headers = [
            "Supplier",
            "Risk Score",
            "Confidence",
            "Positive Sentiment",
            "Negative Sentiment",
            "Neutral Sentiment",
        ];

        const rows = suppliers.map((supplier) => [
            supplier.supplier,
            supplier.risk_score,
            supplier.confidence,
            supplier.sentiment_breakdown.positive,
            supplier.sentiment_breakdown.negative,
            supplier.sentiment_breakdown.neutral,
        ]);

        downloadCsv(
            headers,
            rows,
            "suppliers-export.csv"
        );

        return;
    }

    const shipments = data as ShipmentStatus;

    const headers = [
        "Metric",
        "Value",
    ];

    const rows = [
        ["Total Shipments", shipments.total],
        ["Pending", shipments.pending],
        ["In Transit", shipments.in_transit],
        ["Delivered", shipments.delivered],
        ["Delayed", shipments.delayed],
        ["Cancelled", shipments.cancelled],
    ];

    downloadCsv(
        headers,
        rows,
        "shipments-export.csv"
    );
}
