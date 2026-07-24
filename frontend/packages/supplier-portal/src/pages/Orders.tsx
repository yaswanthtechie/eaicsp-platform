import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useApolloClient, useQuery } from "@apollo/client";

import { GET_PURCHASE_ORDERS } from "../graphql/queries";

import POCard from "../components/POCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Loading from "../components/Loading";
import { TOKEN_KEY } from "../constants/storage";
import type { PurchaseOrder } from "../types/po";

const Orders = () => {
  const navigate = useNavigate();
  const apolloClient = useApolloClient();

  const [filter, setFilter] = useState("All");

  // GraphQL Query
  const { data, loading, error } = useQuery(GET_PURCHASE_ORDERS);

  if (loading) return <Loading />;

  if (error) return <ErrorState />;

  const orders: PurchaseOrder[] = data?.purchaseOrders || [];

  const filteredOrders =
    filter === "All"
      ? orders
      : orders.filter(
          (po: PurchaseOrder) =>
            po.status.toLowerCase() === filter.toLowerCase()
        );

  const handleLogout = async () => {
    localStorage.removeItem(TOKEN_KEY);

    await apolloClient.clearStore();

    navigate("/login");
  };

  return (
    <div className="orders">
      <h1>Purchase Orders</h1>

      <div className="top-buttons">
        <button
          className="invoice-btn"
          onClick={() => navigate("/invoices/new")}
        >
          New Invoice
        </button>

        <button
          className="logout-btn"
          onClick={handleLogout}
        >
          Logout
        </button>
      </div>

      <div className="tabs">
        {["All", "Sent", "Acknowledged", "Fulfilled"].map((tab) => (
          <button
            key={tab}
            className={filter === tab ? "active-tab" : ""}
            onClick={() => setFilter(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {filteredOrders.length === 0 ? (
        <EmptyState />
      ) : (
        filteredOrders.map((order: PurchaseOrder) => (
          <POCard
            key={order.po_number}
            order={order}
          />
        ))
      )}
    </div>
  );
};

export default Orders;