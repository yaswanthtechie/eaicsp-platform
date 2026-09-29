import { useMemo } from "react";
import { NetworkStatus } from "@apollo/client";
import { useNavigate } from "react-router-dom";

import { usePurchaseOrders } from "../hooks/usePurchaseOrders";

interface DashboardPurchaseOrder {
  poNumber: string;
  supplierId: string;
  status: string;
  totalAmount: number;
  expectedDelivery: string;
  items: unknown[];
}

interface DashboardPurchaseOrderEdge {
  cursor: string;
  node: DashboardPurchaseOrder;
}

export default function Dashboard() {
  const navigate = useNavigate();

  const {
    data,
    loading,
    error,
    networkStatus,
  } = usePurchaseOrders({
    first: 100,
  });

  const purchaseOrders = useMemo<
    DashboardPurchaseOrder[]
  >(
    () =>
      (
        data?.purchaseOrders?.edges as
          | DashboardPurchaseOrderEdge[]
          | undefined
      )?.map(
        (edge: DashboardPurchaseOrderEdge) =>
          edge.node,
      ) ?? [],
    [data],
  );

  const totalPOs = purchaseOrders.length;

  const pendingAcknowledgement = useMemo(
    () =>
      purchaseOrders.filter(
        (order: DashboardPurchaseOrder) =>
          order.status === "SENT",
      ),
    [purchaseOrders],
  );

  const acknowledgedPOs = useMemo(
    () =>
      purchaseOrders.filter(
        (order: DashboardPurchaseOrder) =>
          order.status === "ACKNOWLEDGED",
      ),
    [purchaseOrders],
  );

  const totalPOValue = useMemo(
    () =>
      purchaseOrders.reduce(
        (
          total: number,
          order: DashboardPurchaseOrder,
        ) => total + order.totalAmount,
        0,
      ),
    [purchaseOrders],
  );

  const isLoading =
    loading ||
    networkStatus === NetworkStatus.loading;

  if (isLoading) {
    return (
      <main className="dashboard-page">
        <header className="page-header">
          <h1>Supplier Dashboard</h1>

          <p>
            Overview of your purchase
            orders and supplier activity.
          </p>
        </header>

        <div
          className="loading-state"
          role="status"
          aria-label="Loading dashboard"
        >
          Loading dashboard...
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="dashboard-page">
        <header className="page-header">
          <h1>Supplier Dashboard</h1>

          <p>
            Overview of your purchase
            orders and supplier activity.
          </p>
        </header>

        <div
          className="error-state"
          role="alert"
        >
          Something went wrong.
        </div>
      </main>
    );
  }

  return (
    <main className="dashboard-page">
      <header className="page-header">
        <h1>Supplier Dashboard</h1>

        <p>
          Overview of your purchase
          orders and supplier activity.
        </p>
      </header>

      <section
        className="dashboard-summary"
        aria-label="Purchase order summary"
      >
        <article className="dashboard-card">
          <span className="dashboard-card-label">
            Total POs
          </span>

          <strong className="dashboard-card-value">
            {totalPOs}
          </strong>
        </article>

        <article className="dashboard-card">
          <span className="dashboard-card-label">
            Pending Acknowledgement
          </span>

          <strong className="dashboard-card-value">
            {pendingAcknowledgement.length}
          </strong>
        </article>

        <article className="dashboard-card">
          <span className="dashboard-card-label">
            Acknowledged
          </span>

          <strong className="dashboard-card-value">
            {acknowledgedPOs.length}
          </strong>
        </article>

        <article className="dashboard-card">
          <span className="dashboard-card-label">
            Total PO Value
          </span>

          <strong className="dashboard-card-value">
            ₹
            {totalPOValue.toLocaleString(
              "en-IN",
              {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              },
            )}
          </strong>
        </article>
      </section>

      <section
        className="dashboard-actions"
        aria-labelledby="quick-actions-heading"
      >
        <h2 id="quick-actions-heading">
          Quick Actions
        </h2>

        <div className="quick-actions">
          <button
            type="button"
            onClick={() =>
              navigate("/orders")
            }
          >
            View Purchase Orders
          </button>

          <button
            type="button"
            onClick={() =>
              navigate("/shipments")
            }
          >
            Track Shipments
          </button>
        </div>
      </section>

      <section
        className="dashboard-notifications"
        aria-labelledby="action-items-heading"
      >
        <h2 id="action-items-heading">
          Action Items
        </h2>

        <div className="dashboard-action-list">
          {pendingAcknowledgement.length >
            0 && (
            <article className="dashboard-action-card">
              <div>
                <h3>
                  Purchase Orders Awaiting
                  Acknowledgement
                </h3>

                <p>
                  {
                    pendingAcknowledgement.length
                  }{" "}
                  POs waiting for
                  acknowledgement
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  navigate("/orders")
                }
              >
                Review POs
              </button>
            </article>
          )}

          {acknowledgedPOs.length > 0 && (
            <article className="dashboard-action-card">
              <div>
                <h3>
                  Purchase Orders Ready
                  for Invoicing
                </h3>

                <p>
                  {acknowledgedPOs.length}{" "}
                  {acknowledgedPOs.length ===
                  1
                    ? "acknowledged PO"
                    : "acknowledged POs"}{" "}
                  ready for invoicing
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  navigate("/invoices/new")
                }
              >
                Create Invoice
              </button>
            </article>
          )}

          {pendingAcknowledgement.length ===
            0 &&
            acknowledgedPOs.length ===
              0 && (
              <div className="empty-state">
                <h3>No action items</h3>

                <p>
                  There are no purchase
                  orders requiring your
                  attention.
                </p>
              </div>
            )}
        </div>
      </section>
    </main>
  );
}