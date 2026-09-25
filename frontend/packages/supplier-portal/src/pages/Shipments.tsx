import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getSupplierId,
} from "../auth/tokenStorage";

import {
  getShipments,
  type Shipment,
  type ShipmentStatus,
} from "../api/shipments";

const statusLabels: Record<
  ShipmentStatus,
  string
> = {
  PROCESSING: "Processing",
  IN_TRANSIT: "In Transit",
  OUT_FOR_DELIVERY:
    "Out for Delivery",
  DELIVERED: "Delivered",
};

export default function Shipments() {
  const [shipments, setShipments] =
    useState<Shipment[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadShipments = async () => {
      try {
        setLoading(true);
        setError(null);

        const data =
          await getShipments();

        if (isMounted) {
          setShipments(data);
        }
      } catch {
        if (isMounted) {
          setError(
            "Unable to load shipments. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadShipments();

    return () => {
      isMounted = false;
    };
  }, []);

  const currentSupplierId =
    getSupplierId();

  const sortedShipments = useMemo(() => {
    return shipments
      .filter(
        (shipment) =>
          currentSupplierId !== null &&
          shipment.supplierId ===
            currentSupplierId,
      )
      .sort(
        (a, b) =>
          new Date(
            a.expectedDelivery,
          ).getTime() -
          new Date(
            b.expectedDelivery,
          ).getTime(),
      );
  }, [
    shipments,
    currentSupplierId,
  ]);

  if (loading) {
    return (
      <main className="shipments-page">
        <header className="page-header">
          <h1>
            Shipment Tracking
          </h1>

          <p>
            Track purchase order
            deliveries and shipment
            progress.
          </p>
        </header>

        <div
          className="loading-state"
          role="status"
          aria-label="Loading shipments..."
        >
          Loading shipments...
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="shipments-page">
        <header className="page-header">
          <h1>
            Shipment Tracking
          </h1>

          <p>
            Track purchase order
            deliveries and shipment
            progress.
          </p>
        </header>

        <div
          className="error-state"
          role="alert"
        >
          {error}
        </div>
      </main>
    );
  }

  return (
    <main className="shipments-page">
      <header className="page-header">
        <h1>
          Shipment Tracking
        </h1>

        <p>
          Track purchase order
          deliveries and shipment
          progress.
        </p>
      </header>

      <section
        className="shipment-summary"
        aria-label="Shipment summary"
      >
        <div className="summary-card">
          <span>
            Total Shipments
          </span>

          <strong>
            {sortedShipments.length}
          </strong>
        </div>

        <div className="summary-card">
          <span>
            In Transit
          </span>

          <strong>
            {
              sortedShipments.filter(
                (shipment) =>
                  shipment.status ===
                  "IN_TRANSIT",
              ).length
            }
          </strong>
        </div>

        <div className="summary-card">
          <span>
            Delivered
          </span>

          <strong>
            {
              sortedShipments.filter(
                (shipment) =>
                  shipment.status ===
                  "DELIVERED",
              ).length
            }
          </strong>
        </div>
      </section>

      <section
        aria-labelledby="shipment-list-heading"
      >
        <h2 id="shipment-list-heading">
          Shipments
        </h2>

        {sortedShipments.length ===
        0 ? (
          <div className="empty-state">
            <h3>
              No shipments available
            </h3>

            <p>
              There are currently no
              shipments to track.
            </p>
          </div>
        ) : (
          <div className="shipment-list">
            {sortedShipments.map(
              (shipment) => (
                <article
                  className="shipment-card"
                  key={shipment.id}
                >
                  <div className="shipment-card-header">
                    <div>
                      <h3>
                        {shipment.poNumber}
                      </h3>

                      <p>
                        {shipment.id}
                      </p>
                    </div>

                    <span
                      className={`shipment-status shipment-status-${shipment.status.toLowerCase()}`}
                    >
                      {
                        statusLabels[
                          shipment.status
                        ]
                      }
                    </span>
                  </div>

                  <div className="shipment-details">
                    <p>
                      <strong>
                        Product:
                      </strong>{" "}
                      {shipment.product}
                    </p>

                    <p>
                      <strong>
                        Expected Delivery:
                      </strong>{" "}
                      {
                        shipment.expectedDelivery
                      }
                    </p>
                  </div>

                  <div className="shipment-progress">
                    <div className="progress-header">
                      <span>
                        Delivery Progress
                      </span>

                      <strong>
                        {shipment.progress}%
                      </strong>
                    </div>

                    <div
                      className="progress-track"
                      role="progressbar"
                      aria-valuenow={
                        shipment.progress
                      }
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
              ),
            )}
          </div>
        )}
      </section>
    </main>
  );
}