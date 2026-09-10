import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import { useAcknowledgePO } from "../hooks/useAcknowledgePO";
import { useOrderDetails } from "../hooks/useOrderDetails";

import StatusBadge from "../components/StatusBadge";
import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";

import type { PurchaseOrder } from "../types/po";
import type { PurchaseOrderEdge } from "../types/graphql";

import { formatCurrency } from "../utils/formatCurrency";
import { formatDate } from "../utils/formatDate";

const OrderDetails = () => {
  const { poNumber } = useParams();
  const navigate = useNavigate();

  const { data, loading, error } = useOrderDetails();

  const { acknowledgePO } = useAcknowledgePO();

  // Prevent polling from replacing the page with a loader
 if (loading && !data) {
  return <Loading />;
}

if (error && !data) {
  return <ErrorState />;
}

  const orders: PurchaseOrder[] =
    data?.purchaseOrders?.edges?.map(
      (edge: PurchaseOrderEdge) => edge.node
    ) || [];

  const order = orders.find(
    (po) => po.po_number === poNumber
  );

  // Empty state
  if (!order) {
    return (
      <div style={{ padding: "20px" }}>
        <h2>Purchase Order Not Found</h2>

        <p>
          The requested Purchase Order is not available.
        </p>

        <button
          className="back-btn"
          onClick={() => navigate("/orders")}
        >
          Back to Orders
        </button>
      </div>
    );
  }

  const total = order.items.reduce(
    (sum, item) =>
      sum + item.quantity * item.unit_price,
    0
  );

  // Button click handler
  const handleAcknowledge = async () => {
    if (!poNumber) {
      toast.error("Purchase Order number is missing");
      return;
    }

    try {
      const result = await acknowledgePO(poNumber);

      if (result.queued) {
        toast.success(
          "Purchase Order queued. It will sync when you're online."
        );

        navigate("/orders");
        return;
      }

      toast.success(
        "Purchase Order Acknowledged Successfully"
      );

      navigate("/orders");
    } catch (err) {
      toast.error(
        "Failed to acknowledge Purchase Order"
      );

      console.error(err);
    }
  };

  return (
    <div className="details">
      <h2>Purchase Order Details</h2>

      <div className="detail-card">
        <p>
          <strong>PO Number:</strong>{" "}
          {order.po_number}
        </p>

        <p>
          <strong>Supplier:</strong>{" "}
          {order.supplier_id}
        </p>

        <p>
          <strong>Expected Delivery:</strong>{" "}
          {formatDate(order.expected_delivery)}
        </p>

        <div style={{ margin: "15px 0" }}>
          <StatusBadge status={order.status} />
        </div>
      </div>

      <h3>Items</h3>

      {order.items.length === 0 ? (
        <div style={{ padding: "20px 0" }}>
          <p>
            No items are available for this
            Purchase Order.
          </p>
        </div>
      ) : (
        order.items.map((item) => (
          <div
            key={item.sku}
            className="item-card"
          >
            <h4>{item.product_name}</h4>

            <p>
              <strong>SKU:</strong>{" "}
              {item.sku}
            </p>

            <p>
              <strong>Quantity:</strong>{" "}
              {item.quantity}
            </p>

            <p>
              <strong>Unit Price:</strong>{" "}
              {formatCurrency(item.unit_price)}
            </p>

            <p>
              <strong>Subtotal:</strong>{" "}
              {formatCurrency(
                item.quantity * item.unit_price
              )}
            </p>
          </div>
        ))
      )}

      <h2>
        Total: {formatCurrency(total)}
      </h2>

      {order.status === "sent" && (
        <button
          className="acknowledge-btn"
          onClick={handleAcknowledge}
        >
          Acknowledge
        </button>
      )}

      <button
        className="back-btn"
        onClick={() => navigate("/orders")}
      >
        Back to Orders
      </button>
    </div>
  );
};

export default OrderDetails;