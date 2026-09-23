import type { InventoryItem } from "../types/forecast";

const escapeCsvValue = (
    value: string | number | boolean
): string => {
    const stringValue = String(value);

    if (
        stringValue.includes(",") ||
        stringValue.includes('"') ||
        stringValue.includes("\n")
    ) {
        return `"${stringValue.replace(/"/g, '""')}"`;
    }

    return stringValue;
};

export const exportInventoryCsv = (
    inventory: InventoryItem[]
): void => {
    const headers = [
        "SKU",
        "Product",
        "Category",
        "Warehouse",
        "Quantity On Hand",
        "Reorder Point",
        "Needs Reorder",
        "Average Daily Demand"
    ];

    const rows = inventory.map((item) => [
        item.sku_id,
        item.product_name,
        item.category,
        item.warehouse_id,
        item.quantity_on_hand,
        item.reorder_point,
        item.needs_reorder,
        item.avg_daily_demand
    ]);

    const csvContent = [
        headers,
        ...rows
    ]
        .map((row) =>
            row.map(escapeCsvValue).join(",")
        )
        .join("\n");

    const blob = new Blob(
        [csvContent],
        { type: "text/csv;charset=utf-8;" }
    );

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;
    link.download = "inventory-export.csv";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
};
