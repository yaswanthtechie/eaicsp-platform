import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { NetworkStatus } from "@apollo/client";

import { usePurchaseOrders } from "../hooks/usePurchaseOrders";
import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";
import type { POStatus, PurchaseOrder } from "../types/po";
import type { PurchaseOrderEdge } from "../types/graphql";

import { formatCurrency } from "../utils/formatCurrency";

const Dashboard = () => {
  const navigate = useNavigate();

  const { data, loading, error, networkStatus } =
    usePurchaseOrders({
      first: 100,
    });

  const orders: PurchaseOrder[] = useMemo(
    () =>
      data?.purchaseOrders?.edges?.map(
        (edge: PurchaseOrderEdge) => edge.node
      ) ?? [],
    [data]
  );

  // Only show the full-page loader on the
  // initial request. Polling should not remove
  // the dashboard while it is being viewed.
  if (
    loading &&
    networkStatus === NetworkStatus.loading &&
    !data
  ) {
    return <Loading />;
  }

  if (error && !data) {
    return <ErrorState />;
  }

  const counts: Record<POStatus, number> = {
    DRAFT: 0,
    SENT: 0,
    ACKNOWLEDGED: 0,
    FULFILLED: 0,
    CANCELLED: 0,
  };

  orders.forEach((order) => {
    counts[order.status] += 1;
  });

  const totalValue = orders.reduce(
    (sum, order) => sum + order.totalAmount,
    0
  );

  const pendingAcknowledgement = counts.SENT;

  const acknowledgedOrders = orders.filter(
    (order) => order.status === "ACKNOWLEDGED"
  );

  const pendingInvoiceValue = acknowledgedOrders.reduce(
    (sum, order) => sum + order.totalAmount,
    0
  );

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>Supplier Dashboard</h1>
          <p>
            Overview of your purchase orders and pending
            actions.
          </p>
        </div>
      </header>

      {/* Summary cards */}
      <section
        className="dashboard-summary"
        aria-label="Purchase order summary"
      >
        <div className="dashboard-card">
          <span className="dashboard-card-label">
            Total POs
          </span>

          <strong>{orders.length}</strong>
        </div>

        <div className="dashboard-card">
          <span className="dashboard-card-label">
            Pending Acknowledgement
          </span>

          <strong>{pendingAcknowledgement}</strong>
        </div>

        <div className="dashboard-card">
          <span className="dashboard-card-label">
            Acknowledged
          </span>

          <strong>{counts.ACKNOWLEDGED}</strong>
        </div>

        <div className="dashboard-card">
          <span className="dashboard-card-label">
            Total PO Value
          </span>

          <strong>{formatCurrency(totalValue)}</strong>
        </div>
      </section>

      {/* Status overview */}
      <section
        className="dashboard-section"
        aria-labelledby="status-heading"
      >
        <h2 id="status-heading">
          Purchase Order Status
        </h2>

        <div className="status-grid">
          <button
            type="button"
            className="status-card"
            onClick={() =>
              navigate("/orders?status=DRAFT")
            }
          >
            <span>Draft</span>
            <strong>{counts.DRAFT}</strong>
          </button>

          <button
            type="button"
            className="status-card"
            onClick={() =>
              navigate("/orders?status=SENT")
            }
          >
            <span>Sent</span>
            <strong>{counts.SENT}</strong>
          </button>

          <button
            type="button"
            className="status-card"
            onClick={() =>
              navigate(
                "/orders?status=ACKNOWLEDGED"
              )
            }
          >
            <span>Acknowledged</span>
            <strong>{counts.ACKNOWLEDGED}</strong>
          </button>

          <button
            type="button"
            className="status-card"
            onClick={() =>
              navigate(
                "/orders?status=FULFILLED"
              )
            }
          >
            <span>Fulfilled</span>
            <strong>{counts.FULFILLED}</strong>
          </button>

          <button
            type="button"
            className="status-card"
            onClick={() =>
              navigate(
                "/orders?status=CANCELLED"
              )
            }
          >
            <span>Cancelled</span>
            <strong>{counts.CANCELLED}</strong>
          </button>
        </div>
      </section>

      {/* Pending actions */}
      <section
        className="dashboard-section"
        aria-labelledby="actions-heading"
      >
        <h2 id="actions-heading">
          Pending Actions
        </h2>

        {pendingAcknowledgement > 0 ? (
          <div className="action-card">
            <div>
              <strong>
                {pendingAcknowledgement} PO
                {pendingAcknowledgement !== 1
                  ? "s"
                  : ""}{" "}
                waiting for acknowledgement
              </strong>

              <p>
                Review and acknowledge your sent
                purchase orders.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                navigate("/orders?status=SENT")
              }
            >
              Review POs
            </button>
          </div>
        ) : (
          <div className="dashboard-empty">
            <p>
              No purchase orders are waiting for
              acknowledgement.
            </p>
          </div>
        )}

        {counts.ACKNOWLEDGED > 0 && (
          <div className="action-card">
            <div>
              <strong>
                {counts.ACKNOWLEDGED} acknowledged PO
                {counts.ACKNOWLEDGED !== 1
                  ? "s"
                  : ""}{" "}
                ready for invoicing
              </strong>

              <p>
                Acknowledged purchase orders can be
                used to create invoices.
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
          </div>
        )}
      </section>

      {/* Quick actions */}
      <section
        className="dashboard-section"
        aria-labelledby="quick-actions-heading"
      >
        <h2 id="quick-actions-heading">
          Quick Actions
        </h2>

        <div className="quick-actions">
          <button
            type="button"
            onClick={() => navigate("/orders")}
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

          <button
            type="button"
            onClick={() =>
              navigate("/documents")
            }
          >
            Documents
          </button>

          <button
            type="button"
            onClick={() =>
              navigate("/profile")
            }
          >
            Profile & Settings
          </button>
        </div>
      </section>

      {/* Invoice information */}
      {pendingInvoiceValue > 0 && (
        <section
          className="dashboard-section"
          aria-labelledby="invoice-heading"
        >
          <h2 id="invoice-heading">
            Invoice Overview
          </h2>

          <div className="dashboard-card">
            <span className="dashboard-card-label">
              Value of acknowledged POs
            </span>

            <strong>
              {formatCurrency(
                pendingInvoiceValue
              )}
            </strong>

            <p>
              These POs are currently eligible for
              invoice submission.
            </p>
          </div>
        </section>
      )}
    </main>
  );
};

export default Dashboard;