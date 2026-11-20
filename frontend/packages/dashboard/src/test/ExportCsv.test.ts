import { afterEach, describe, expect, it, vi } from "vitest";
import type { InventoryItem } from "../types/forecast";
import type {
    ShipmentStatus,
    SupplierRiskItem,
} from "../types/dashboard";
import { exportDashboardCsv } from "../utils/exportCsv";

describe("exportDashboardCsv", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("creates and downloads the inventory CSV file", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "Kestrel Sticky Notes - Pack of 10 1",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn(() => "blob:test");
        const revokeObjectURL = vi.fn();
        const click = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL,
        });

        const link = document.createElement("a");
        link.click = click;

        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: {
                "SKU-000001": 'Kestrel Sticky Notes - Pack of 10 1, "Premium"\nPack (SKU-000001)"',
            },
            warehouseNames: {},
        });

        expect(createObjectURL).toHaveBeenCalledTimes(1);
        expect(link.download).toBe("inventory-export.csv");
        expect(click).toHaveBeenCalledTimes(1);
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
    });

    it("escapes commas, quotes and new lines", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: 'Kestrel Sticky Notes - Pack of 10 1, "Premium"\nPack (SKU-000001)"',
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();
        const revokeObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL,
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: {
                "SKU-000001": 'Kestrel Sticky Notes - Pack of 10 1, "Premium"\nPack',
            },
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain('"Kestrel Sticky Notes - Pack of 10 1, ""Premium""\nPack (SKU-000001)"');
    });

    it("protects values starting with =", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "=SUM(A1:A2)",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: { "SKU-000001": "=SUM(A1:A2)" },
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain("'=SUM(A1:A2)");
    });

    it("protects values starting with +", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "+123",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: { "SKU-000001": "+123" },
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain("'+123");
    });

    it("protects values starting with -", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "-123",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: { "SKU-000001": "-123" },
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain("'-123");
    });

    it("protects values starting with @", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "@SUM(A1:A2)",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 100,
                reorder_point: 20,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: { "SKU-000001": "@SUM(A1:A2)" },
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain("'@SUM(A1:A2)");
    });

    it("exports supplier data", async () => {
        const suppliers: SupplierRiskItem[] = [
            {
                supplier: "Big Basket",
                risk_score: 0.81,
                confidence: 0.94,
                sentiment_breakdown: {
                    positive: 0.1,
                    negative: 0.7,
                    neutral: 0.2,
                },
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("suppliers", suppliers);

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(link.download).toBe("suppliers-export.csv");
        expect(csv).toContain(
            "Supplier,Risk Score,Confidence,Positive Sentiment,Negative Sentiment,Neutral Sentiment"
        );
        expect(csv).toContain(
            "Big Basket,0.81,0.94,0.1,0.7,0.2"
        );
    });

    it("exports shipment data", async () => {
        const shipments: ShipmentStatus = {
            total: 150,
            pending: 20,
            in_transit: 28,
            delivered: 82,
            delayed: 10,
            cancelled: 10,
        };

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("shipments", shipments);

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(link.download).toBe("shipments-export.csv");
        expect(csv).toContain("Metric,Value");
        expect(csv).toContain("Total Shipments,150");
        expect(csv).toContain("Pending,20");
        expect(csv).toContain("In Transit,28");
        expect(csv).toContain("Delivered,82");
        expect(csv).toContain("Delayed,10");
        expect(csv).toContain("Cancelled,10");
    });

    it("does not prefix negative numbers", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "Kestrel Sticky Notes - Pack of 10 1",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: -5,
                reorder_point: 20,
                needs_reorder: true,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn((blob: Blob) => {
            expect(blob).toBeInstanceOf(Blob);
            return "blob:test";
        });

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory);

        const csv = await createObjectURL.mock.calls[0][0].text();

        expect(csv).toContain(",-5,");
        expect(csv).not.toContain("'-5");
    });


    it("exports product and warehouse names along with their IDs", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "Kestrel Sticky Notes - Pack of 10 1",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 120,
                reorder_point: 50,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: {
                "SKU-000001": "Kestrel Sticky Notes - Pack of 10 1",
            },
            warehouseNames: {
                "WH-BLR-01": "Bangalore Warehouse",
            },
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain(
            "Kestrel Sticky Notes - Pack of 10 1 (SKU-000001)",
        );
        expect(csv).toContain(
            "Bangalore Warehouse (WH-BLR-01)",
        );
    });

    it("falls back to the product names and warehouse ID when names are missing", async () => {
        const inventory: InventoryItem[] = [
            {
                sku_id: "SKU-000001",
                product_name: "Kestrel Sticky Notes - Pack of 10 1",
                category: "Stationery",
                warehouse_id: "WH-BLR-01",
                quantity_on_hand: 120,
                reorder_point: 50,
                needs_reorder: false,
                avg_daily_demand: 10,
            },
        ];

        const createObjectURL = vi.fn();

        vi.stubGlobal("URL", {
            createObjectURL,
            revokeObjectURL: vi.fn(),
        });

        const link = document.createElement("a");
        vi.spyOn(document, "createElement").mockReturnValue(link);

        exportDashboardCsv("inventory", inventory, {
            productNames: {},
            warehouseNames: {},
        });

        const blob = createObjectURL.mock.calls[0][0] as Blob;
        const csv = await blob.text();

        expect(csv).toContain("SKU-000001");
        expect(csv).toContain("WH-BLR-01");
        expect(csv).toContain("Kestrel Sticky Notes - Pack of 10 1");
    });
});
