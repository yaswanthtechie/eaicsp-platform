import { useState } from "react";
import { useNavigate } from "react-router-dom";

import POCard from "../components/POCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Loading from "../components/Loading";
import { logout } from "../auth/logout";
import type { PurchaseOrder } from "../types/po";
import { usePurchaseOrders } from "../hooks/usePurchaseOrders";

import type { PurchaseOrderEdge } from "../types/graphql";
import { ORDERS_PER_PAGE } from "../constants/pagination";

const Orders = () => {
  const navigate = useNavigate();

  const [filter, setFilter] = useState("All");
  const [poNumber, setPoNumber] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const { data, loading, error, fetchMore } = usePurchaseOrders({
    first: ORDERS_PER_PAGE,
    after: null,
    status: filter === "All" ? undefined : filter.toLowerCase(),
    poNumber: poNumber || undefined,
    minAmount: minAmount ? Number(minAmount) : undefined,
    maxAmount: maxAmount ? Number(maxAmount) : undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
  });

  if (loading && !data) return <Loading />;

  if (error && !data) return <ErrorState />;

  const orders: PurchaseOrder[] =
    data?.purchaseOrders?.edges?.map(
      (edge: PurchaseOrderEdge) => edge.node
    ) || [];

  const handleLoadMore = () => {
    if (!data?.purchaseOrders?.pageInfo?.endCursor) {
      return;
    }

    fetchMore({
      variables: {
        first: ORDERS_PER_PAGE,
        after: data.purchaseOrders.pageInfo.endCursor,
        status: filter === "All" ? undefined : filter.toLowerCase(),
        poNumber: poNumber || undefined,
        minAmount: minAmount ? Number(minAmount) : undefined,
        maxAmount: maxAmount ? Number(maxAmount) : undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      },
    });
  };

  return (
    <div className="orders">
      <h1>Purchase Orders</h1>

      <div className="search-filters">
        <input
          type="text"
          placeholder="Search PO Number"
          value={poNumber}
          onChange={(e) => setPoNumber(e.target.value)}
        />

        <input
          type="number"
          placeholder="Min Amount"
          value={minAmount}
          onChange={(e) => setMinAmount(e.target.value)}
        />

        <input
          type="number"
          placeholder="Max Amount"
          value={maxAmount}
          onChange={(e) => setMaxAmount(e.target.value)}
        />

        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />

        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
      </div>

      <div className="top-buttons">
        <button
          className="invoice-btn"
          onClick={() => navigate("/invoices/new")}
        >
          New Invoice
        </button>

        <button
          className="logout-btn"
          onClick={logout}
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

      {orders.length === 0 ? (
        <EmptyState />
      ) : (
        orders.map((order) => (
          <POCard
            key={order.po_number}
            order={order}
          />
        ))
      )}

      {data?.purchaseOrders?.pageInfo?.hasNextPage && (
        <button
          className="load-more-btn"
          onClick={handleLoadMore}
        >
          Load More
        </button>
      )}
    </div>
  );
};

export default Orders;