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
    <div className="card">

      <div className="card-top">

        <h3>{order.po_number}</h3>

        <StatusBadge status={order.status} />

      </div>

      <p>
        Total : {formatCurrency(order.total_amount)}
      </p>

      <p>
        Delivery :{" "}
        {new Date(order.expected_delivery).toLocaleDateString("en-IN")}
      </p>

      <Link to={`/orders/${order.po_number}`}>
        <button>View Details</button>
      </Link>

    </div>
  );
};

export default POCard;