import type { PurchaseOrder } from "../types/po";

export const purchaseOrders: PurchaseOrder[] = [
  {
    po_number: "PO1001",
    supplier_id: "SUP001",
    status: "sent",
    total_amount: 12000,
    expected_delivery: "2026-07-25",
    items: [
      {
        sku: "SKU001",
        product_name: "Laptop",
        quantity: 2,
        unit_price: 5000,
      },
      {
        sku: "SKU002",
        product_name: "Mouse",
        quantity: 10,
        unit_price: 200,
      },
    ],
  },
  {
    po_number: "PO1002",
    supplier_id: "SUP001",
    status: "acknowledged",
    total_amount: 18000,
    expected_delivery: "2026-07-28",
    items: [
      {
        sku: "SKU003",
        product_name: "Keyboard",
        quantity: 20,
        unit_price: 500,
      },
      {
        sku: "SKU004",
        product_name: "Monitor",
        quantity: 5,
        unit_price: 1600,
      },
    ],
  },
  {
    po_number: "PO1003",
    supplier_id: "SUP002",
    status: "fulfilled",
    total_amount: 22000,
    expected_delivery: "2026-07-20",
    items: [
      {
        sku: "SKU005",
        product_name: "Printer",
        quantity: 4,
        unit_price: 4000,
      },
      {
        sku: "SKU006",
        product_name: "Scanner",
        quantity: 2,
        unit_price: 3000,
      },
    ],
  },
  {
    po_number: "PO1004",
    supplier_id: "SUP003",
    status: "draft",
    total_amount: 15000,
    expected_delivery: "2026-08-02",
    items: [
      {
        sku: "SKU007",
        product_name: "CPU",
        quantity: 3,
        unit_price: 4000,
      },
      {
        sku: "SKU008",
        product_name: "RAM",
        quantity: 8,
        unit_price: 500,
      },
    ],
  },
  {
    po_number: "PO1005",
    supplier_id: "SUP002",
    status: "cancelled",
    total_amount: 9000,
    expected_delivery: "2026-08-05",
    items: [
      {
        sku: "SKU009",
        product_name: "SSD",
        quantity: 5,
        unit_price: 1200,
      },
      {
        sku: "SKU010",
        product_name: "USB Drive",
        quantity: 20,
        unit_price: 150,
      },
    ],
  },
  {
    po_number: "PO1006",
    supplier_id: "SUP004",
    status: "sent",
    total_amount: 30000,
    expected_delivery: "2026-08-08",
    items: [
      {
        sku: "SKU011",
        product_name: "Projector",
        quantity: 3,
        unit_price: 8000,
      },
      {
        sku: "SKU012",
        product_name: "HDMI Cable",
        quantity: 10,
        unit_price: 600,
      },
    ],
  },
  {
    po_number: "PO1007",
    supplier_id: "SUP005",
    status: "fulfilled",
    total_amount: 27000,
    expected_delivery: "2026-08-10",
    items: [
      {
        sku: "SKU013",
        product_name: "Tablet",
        quantity: 6,
        unit_price: 4000,
      },
      {
        sku: "SKU014",
        product_name: "Stylus",
        quantity: 6,
        unit_price: 500,
      },
    ],
  },
  {
    po_number: "PO1008",
    supplier_id: "SUP005",
    status: "acknowledged",
    total_amount: 10000,
    expected_delivery: "2026-08-15",
    items: [
      {
        sku: "SKU015",
        product_name: "Router",
        quantity: 5,
        unit_price: 1500,
      },
      {
        sku: "SKU016",
        product_name: "LAN Cable",
        quantity: 20,
        unit_price: 125,
      },
    ],
  },
];