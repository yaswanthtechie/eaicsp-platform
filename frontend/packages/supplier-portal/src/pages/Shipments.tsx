import { useMemo } from "react";

type ShipmentStatus =
  | "PROCESSING"
  | "IN_TRANSIT"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED";

interface Shipment {
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

const statusLabels: Record<ShipmentStatus, string> = {
  PROCESSING: "Processing",
  IN_TRANSIT: "In Transit",
  OUT_FOR_DELIVERY: "Out for Delivery",
  DELIVERED: "Delivered",
};

export default function Shipments() {
  const sortedShipments = useMemo(
    () =>
      [...shipments].sort(
        (a, b) =>
          new Date(a.expectedDelivery).getTime() -
          new Date(b.expectedDelivery).getTime(),
      ),
    [],
  );

  return (
    <main className="shipments-page">
      <header className="page-header">
        <h1>Shipment Tracking</h1>
        <p>Track purchase order deliveries and shipment progress.</p>
      </header>

      <section
        className="shipment-summary"
        aria-label="Shipment summary"
      >
        <div className="summary-card">
          <span>Total Shipments</span>
          <strong>{sortedShipments.length}</strong>
        </div>

        <div className="summary-card">
          <span>In Transit</span>
          <strong>
            {
              sortedShipments.filter(
                (shipment) => shipment.status === "IN_TRANSIT",
              ).length
            }
          </strong>
        </div>

        <div className="summary-card">
          <span>Delivered</span>
          <strong>
            {
              sortedShipments.filter(
                (shipment) => shipment.status === "DELIVERED",
              ).length
            }
          </strong>
        </div>
      </section>

      <section aria-labelledby="shipment-list-heading">
        <h2 id="shipment-list-heading">Shipments</h2>

        {sortedShipments.length === 0 ? (
          <div className="empty-state">
            <h3>No shipments available</h3>
            <p>There are currently no shipments to track.</p>
          </div>
        ) : (
          <div className="shipment-list">
            {sortedShipments.map((shipment) => (
              <article
                className="shipment-card"
                key={shipment.id}
              >
                <div className="shipment-card-header">
                  <div>
                    <h3>{shipment.poNumber}</h3>
                    <p>{shipment.id}</p>
                  </div>

                  <span
                    className={`shipment-status shipment-status-${shipment.status.toLowerCase()}`}
                  >
                    {statusLabels[shipment.status]}
                  </span>
                </div>

                <div className="shipment-details">
                  <p>
                    <strong>Product:</strong> {shipment.product}
                  </p>

                  <p>
                    <strong>Supplier:</strong> {shipment.supplierId}
                  </p>

                  <p>
                    <strong>Expected Delivery:</strong>{" "}
                    {shipment.expectedDelivery}
                  </p>
                </div>

                <div className="shipment-progress">
                  <div className="progress-header">
                    <span>Delivery Progress</span>
                    <strong>{shipment.progress}%</strong>
                  </div>

                  <div
                    className="progress-track"
                    role="progressbar"
                    aria-valuenow={shipment.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${shipment.poNumber} delivery progress`}
                  >
                    <div
                      className="progress-bar"
                      style={{
                        width: `${shipment.progress}%`,
                      }}
                    />
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}