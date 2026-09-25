import { afterEach, describe, expect, it, vi } from "vitest";

import { exportDashboardPdf } from "../utils/exportPdf";

const textMock = vi.fn();
const saveMock = vi.fn();

vi.mock("jspdf", () => ({
    jsPDF: class {
        setFontSize = vi.fn();

        setFont = vi.fn();

        text = textMock;

        splitTextToSize = vi.fn(
            (text: string) => [text]
        );

        addPage = vi.fn();

        save = saveMock;
    },
}));

describe("exportDashboardPdf", () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    const inventory = [
        {
            sku_id: "SKU001",
            product_name: "Rice",
            category: "Food",
            warehouse_id: "WH001",
            quantity_on_hand: 100,
            reorder_point: 20,
            needs_reorder: false,
            avg_daily_demand: 10,
        },
    ];

    const suppliers = [
        {
            supplier: "Big Basket",
            risk_score: 0.81,
            confidence: 0.94,
            sentiment_breakdown: {
                positive: 0.6,
                negative: 0.1,
                neutral: 0.3,
            },
        },
    ];

    const shipments = {
        total: 150,
        pending: 20,
        in_transit: 28,
        delivered: 82,
        delayed: 10,
        cancelled: 10,
    };

    const filters = {
        warehouse: "WH001",
        category: "Food",
        startDate: "2026-09-01",
        endDate: "2026-09-24",
    };

    const kpis = [
        {
            title: "Forecast Accuracy",
            value: 90,
        },
    ];

    it("exports PDF for CEO", async () => {
        await exportDashboardPdf({
            role: "ceo",
            inventory,
            suppliers,
            shipments,
            filters,
            kpis,
        });

        expect(textMock).toHaveBeenCalledWith(
            "Supplier Risk",
            20,
            182
        );

        expect(saveMock).toHaveBeenCalledWith(
            "executive-dashboard-report.pdf"
        );
    });

    it("exports PDF for warehouse manager", async () => {
        await exportDashboardPdf({
            role: "warehouse_manager",
            inventory,
            suppliers,
            shipments,
            filters,
            kpis,
        });

        expect(textMock).toHaveBeenCalledWith(
            "Role: Warehouse Manager",
            20,
            30
        );

        expect(textMock).toHaveBeenCalledWith(
            ["Warehouse: WH001"],
            20,
            50
        );

        expect(textMock).toHaveBeenCalledWith(
            ["Category: Food"],
            20,
            56
        );

        expect(textMock).toHaveBeenCalledWith(
            ["SKU001 | Rice | WH001 | Qty: 100"],
            20,
            190
        );

        expect(
            textMock.mock.calls.some(
                (call) => call[0] === "Supplier Risk"
            )
        ).toBe(false);

        expect(saveMock).toHaveBeenCalledWith(
            "executive-dashboard-report.pdf"
        );
    });
});