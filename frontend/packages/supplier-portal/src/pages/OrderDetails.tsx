import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import { useAcknowledgePO } from "../hooks/useAcknowledgePO";
import { useOrderDetails } from "../hooks/useOrderDetails";

import { GET_PURCHASE_ORDERS } from "../graphql/queries";

import StatusBadge from "../components/StatusBadge";
import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";

import type { PurchaseOrder } from "../types/po";

import type {
  PurchaseOrderEdge,
  PurchaseOrdersQuery,
  AcknowledgePurchaseOrderMutation,
} from "../types/graphql";

import { formatCurrency } from "../utils/formatCurrency";
import { formatDate } from "../utils/formatDate";

import { ORDER_DETAILS_PAGE_SIZE } from "../constants/pagination";

const OrderDetails = () => {
  const { poNumber } = useParams();
  const navigate = useNavigate();

  const { data, loading, error } = useOrderDetails();

  const { acknowledgePurchaseOrder } =
    useAcknowledgePO();

  // Show loading only when there is no existing data.
  // This prevents polling from replacing the page
  // with a loading spinner.
  if (loading && !data) {
    return <Loading />;
  }

  if (error) {
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

  const acknowledgePO = async () => {
    try {
      await acknowledgePurchaseOrder({
        variables: {
          po_number: poNumber,
        },

        optimisticResponse: {
          acknowledgePurchaseOrder: {
            __typename: "PurchaseOrder",
            ...order,
            status: "acknowledged",
          },
        },

        update(
          cache,
          {
            data,
          }: {
            data?: AcknowledgePurchaseOrderMutation;
          }
        ) {
          const existing =
            cache.readQuery<PurchaseOrdersQuery>({
              query: GET_PURCHASE_ORDERS,
              variables: {
                first: ORDER_DETAILS_PAGE_SIZE,
                after: null,
              },
            });

          if (!existing?.purchaseOrders) {
            return;
          }

          cache.writeQuery<PurchaseOrdersQuery>({
            query: GET_PURCHASE_ORDERS,
            variables: {
              first: ORDER_DETAILS_PAGE_SIZE,
              after: null,
            },
            data: {
              purchaseOrders: {
                ...existing.purchaseOrders,

                edges:
                  existing.purchaseOrders.edges.map(
                    (edge: PurchaseOrderEdge) => ({
                      ...edge,

                      node:
                        edge.node.po_number ===
                        poNumber
                          ? data?.acknowledgePurchaseOrder ??
                            edge.node
                          : edge.node,
                    })
                  ),
              },
            },
          });
        },
      });

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
    <div className="order-details">
      <h2>Purchase Order Details</h2>

      <div className="detail-card">
        <p>
          <strong>PO Number :</strong>{" "}
          {order.po_number}
        </p>

        <p>
          <strong>Supplier :</strong>{" "}
          {order.supplier_id}
        </p>

        <p>
          <strong>Expected Delivery :</strong>{" "}
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
              <strong>SKU :</strong>{" "}
              {item.sku}
            </p>

            <p>
              <strong>Quantity :</strong>{" "}
              {item.quantity}
            </p>

            <p>
              <strong>Unit Price :</strong>{" "}
              {formatCurrency(item.unit_price)}
            </p>

            <p>
              <strong>Subtotal :</strong>{" "}
              {formatCurrency(
                item.quantity * item.unit_price
              )}
            </p>
          </div>
        ))
      )}

      <h2>
        Total : {formatCurrency(total)}
      </h2>

      {order.status === "sent" && (
        <button
          className="acknowledge-btn"
          onClick={acknowledgePO}
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