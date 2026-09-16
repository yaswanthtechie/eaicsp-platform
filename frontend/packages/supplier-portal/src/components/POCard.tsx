import { Link } from "react-router-dom";
import type { PurchaseOrder } from "../types/po";
import StatusBadge from "./StatusBadge";

interface Props {
  order: PurchaseOrder;
}

const POCard = ({ order }: Props) => {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
    }).format(amount);
  };

  return (
    <div className="card" data-testid="po-card">
      <div className="card-top">
        <h3>{order.poNumber}</h3>

        <StatusBadge status={order.status} />
      </div>

      <p>Total : {formatCurrency(order.totalAmount)}</p>

      <p>
        Delivery :{" "}
        {new Date(order.expectedDelivery).toLocaleDateString("en-IN")}
      </p>

      <Link to={`/orders/${order.poNumber}`}>
        <button type="button">View Details</button>
      </Link>
    </div>
  );
};

export default POCard;