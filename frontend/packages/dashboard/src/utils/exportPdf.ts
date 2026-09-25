import type {jsPDF} from "jspdf";
import type { InventoryItem } from "../types/forecast";
import type { SupplierRiskItem, ShipmentStatus } from "../types/dashboard";
import type { UserRole } from "../mocks/user";

interface PdfExportData {
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

const addSectionTitle = (
    doc: jsPDF,
    title: string,
    y: number
): number => {
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text(title, 20, y);

    return y + 8;
};

const addText = (
    doc: jsPDF,
    text: string,
    y: number
): number => {
    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");

    const lines = doc.splitTextToSize(text, 170);
    doc.text(lines, 20, y);

    return y + 6 * lines.length;
};

const checkPageSpace = (
    doc: jsPDF,
    y: number
): number => {
    if (y > 275) {
        doc.addPage();
        return 20;
    }

    return y;
};

export const exportDashboardPdf = async ({
    role,
    inventory,
    suppliers,
    shipments,
    filters,
    kpis
}: PdfExportData): Promise<void> => {
    const {jsPDF: JsPdf} = await import("jspdf");
    
    const doc = new JsPdf();

    let y = 20;

    doc.setFontSize(20);
    doc.setFont("helvetica", "bold");
    doc.text("Executive Dashboard Report", 20, y);

    y += 10;

    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");

    const roleLabel =
        role === "ceo"
            ? "CEO"
            : "Warehouse Manager";

    doc.text(`Role: ${roleLabel}`, 20, y);

    y += 12;

    y = addSectionTitle(
        doc,
        "Dashboard Filters",
        y
    );

    y = addText(
        doc,
        `Warehouse: ${filters.warehouse}`,
        y
    );

    y = addText(
        doc,
        `Category: ${filters.category}`,
        y
    );

    y = addText(
        doc,
        `Start Date: ${filters.startDate || "Not selected"}`,
        y
    );

    y = addText(
        doc,
        `End Date: ${filters.endDate || "Not selected"}`,
        y
    );

    y += 6;

    y = addSectionTitle(
        doc,
        "KPI Summary",
        y
    );

    kpis.forEach((kpi) => {
        y = checkPageSpace(doc, y);

        y = addText(
            doc,
            `${kpi.title}: ${kpi.value}`,
            y
        );
    });

    y += 6;

    y = addSectionTitle(
        doc,
        "Inventory Summary",
        y
    );

    const lowStockItems = inventory.filter(
        (item) => item.needs_reorder
    );

    y = addText(
        doc,
        `Filtered Inventory Items: ${inventory.length}`,
        y
    );

    y = addText(
        doc,
        `Low Stock Items: ${lowStockItems.length}`,
        y
    );

    const totalUnits = inventory.reduce(
        (total, item) =>
            total + item.quantity_on_hand,
        0
    );

    y = addText(
        doc,
        `Total Units: ${totalUnits}`,
        y
    );

    y += 6;

    y = addSectionTitle(
        doc,
        "Shipment Status",
        y
    );

    y = addText(
        doc,
        `Total Shipments: ${shipments.total}`,
        y
    );

    y = addText(
        doc,
        `Pending: ${shipments.pending}`,
        y
    );

    y = addText(
        doc,
        `In Transit: ${shipments.in_transit}`,
        y
    );

    y = addText(
        doc,
        `Delivered: ${shipments.delivered}`,
        y
    );

    y = addText(
        doc,
        `Delayed: ${shipments.delayed}`,
        y
    );

    y = addText(
        doc,
        `Cancelled: ${shipments.cancelled}`,
        y
    );

    if (role === "ceo") {
        y += 6;

        y = checkPageSpace(doc, y);

        y = addSectionTitle(
            doc,
            "Supplier Risk",
            y
        );

        suppliers.forEach((supplier) => {
            y = checkPageSpace(doc, y);

            y = addText(
                doc,
                `${supplier.supplier}: Risk ${supplier.risk_score}`,
                y
            );

        });
    }

    y += 6;

    y = checkPageSpace(doc, y);

    y = addSectionTitle(
        doc,
        "Inventory Details",
        y
    );

    inventory.slice(0, 40).forEach((item) => {
        y = checkPageSpace(doc, y);

        const line =
            `${item.sku_id} | ${item.product_name} | ` +
            `${item.warehouse_id} | Qty: ${item.quantity_on_hand}`;

        y = addText(doc, line, y);
    });

    if (inventory.length > 40) {
        y = checkPageSpace(doc, y);

        y = addText(
            doc,
            `Showing first 40 of ${inventory.length} filtered inventory items.`,
            y
        );
    }

    doc.save("executive-dashboard-report.pdf");
};