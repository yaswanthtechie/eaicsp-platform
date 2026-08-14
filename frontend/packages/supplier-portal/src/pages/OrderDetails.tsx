import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@apollo/client";

import { GET_PURCHASE_ORDERS } from "../graphql/queries";
import { ACKNOWLEDGE_PO } from "../graphql/mutations";

import StatusBadge from "../components/StatusBadge";
import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";

import type { PurchaseOrder } from "../types/po";
import { toast } from "react-toastify";

const OrderDetails = () => {
  const { poNumber } = useParams();
  const navigate = useNavigate();

  const { data, loading, error } = useQuery(GET_PURCHASE_ORDERS);

  const [acknowledgePurchaseOrder] = useMutation(ACKNOWLEDGE_PO);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
    }).format(amount);
  };

  if (loading) return <Loading />;

  if (error) return <ErrorState />;

  const orders: PurchaseOrder[] = data?.purchaseOrders || [];

  const order = orders.find(
    (po) => po.po_number === poNumber
  );

  if (!order) {
    return (
      <div style={{ padding: "20px" }}>
        <h2>Purchase Order Not Found</h2>

        <button onClick={() => navigate("/orders")}>
          Back
        </button>
      </div>
    );
  }

  const total = order.items.reduce(
    (sum, item) => sum + item.quantity * item.unit_price,
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

        update(cache, { data }) {
          const existing = cache.readQuery<{
            purchaseOrders: PurchaseOrder[];
          }>({
            query: GET_PURCHASE_ORDERS,
          });

          if (!existing) return;

          cache.writeQuery({
            query: GET_PURCHASE_ORDERS,
            data: {
              purchaseOrders: existing.purchaseOrders.map((po) =>
                po.po_number === poNumber
                  ? data?.acknowledgePurchaseOrder ?? po
                  : po
              ),
            },
          });
        },
      });

      toast.success("Purchase Order Acknowledged Successfully");

      navigate("/orders");
    } catch (err) {
      toast.error("Failed to acknowledge Purchase Order");
      console.error(err);
    }
  };

  return (
    <div className="details">
      <h2>Purchase Order Details</h2>

      <div className="detail-card">
        <p>
          <strong>PO Number :</strong> {order.po_number}
        </p>

        <p>
          <strong>Supplier :</strong> {order.supplier_id}
        </p>

        <p>
          <strong>Expected Delivery :</strong>{" "}
          {new Date(order.expected_delivery).toLocaleDateString("en-IN")}
        </p>

        <div style={{ margin: "15px 0" }}>
          <StatusBadge status={order.status} />
        </div>
      </div>

      <h3>Items</h3>

      {order.items.map((item) => (
        <div
          key={item.sku}
          className="item-card"
        >
          <h4>{item.product_name}</h4>

          <p>
            <strong>SKU :</strong> {item.sku}
          </p>

          <p>
            <strong>Quantity :</strong> {item.quantity}
          </p>

          <p>
            <strong>Unit Price :</strong>{" "}
            {formatCurrency(item.unit_price)}
          </p>

          <p>
            <strong>Subtotal :</strong>{" "}
            {formatCurrency(item.quantity * item.unit_price)}
          </p>
        </div>
      ))}

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