export type ShipmentStatus =
  | "PROCESSING"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED";

export interface Shipment {
  id: string;
  poNumber: string;
  supplierId: string;
  product: string;
  expectedDelivery: string;
  status: ShipmentStatus;
  progress: number;
}

const shipments: Shipment[] = [
  {
    id: "SHP-1001",
    poNumber: "PO1001",
    supplierId: "SUP001",
    product: "Laptop",
    expectedDelivery: "2026-08-01",
    status: "PROCESSING",
    progress: 25,
  },
  {
    id: "SHP-1002",
    poNumber: "PO1002",
    supplierId: "SUP001",
    product: "Monitor",
    expectedDelivery: "2026-08-05",
    status: "IN_TRANSIT",
    progress: 65,
  },
  {
    id: "SHP-1003",
    poNumber: "PO1003",
    supplierId: "SUP002",
    product: "Keyboard",
    expectedDelivery: "2026-08-08",
    status: "OUT_FOR_DELIVERY",
    progress: 90,
  },
  {
    id: "SHP-1004",
    poNumber: "PO1004",
    supplierId: "SUP003",
    product: "Server Equipment",
    expectedDelivery: "2026-08-10",
    status: "DELIVERED",
    progress: 100,
  },
];

export const getShipments = async (): Promise<Shipment[]> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(shipments);
    }, 300);
  });
};