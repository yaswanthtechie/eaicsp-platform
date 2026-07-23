import { Link } from "react-router-dom";
import type { PurchaseOrder } from "../types/po";
import StatusBadge from "./StatusBadge";

interface Props {
  order: PurchaseOrder;
}

const POCard = ({ order }: Props) => {
  return (
    <div className="card">

      <div className="card-top">

        <h3>{order.po_number}</h3>

        <StatusBadge status={order.status} />

      </div>

      <p>Total : ₹{order.total_amount}</p>

      <p>Delivery : {order.expected_delivery}</p>

      <Link to={`/orders/${order.po_number}`}>
        <button>View Details</button>
      </Link>

    </div>
  );
};

export default POCard;