import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NetworkStatus } from "@apollo/client";
import { useVirtualizer } from "@tanstack/react-virtual";

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

  const parentRef = useRef<HTMLDivElement>(null);

  const {
    data,
    loading,
    error,
    fetchMore,
    networkStatus,
  } = usePurchaseOrders({
    first: ORDERS_PER_PAGE,
    after: null,
    status: filter === "All" ? undefined : filter.toLowerCase(),
    poNumber: poNumber || undefined,
    minAmount: minAmount ? Number(minAmount) : undefined,
    maxAmount: maxAmount ? Number(maxAmount) : undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
  });

  const loadingMore =
    networkStatus === NetworkStatus.fetchMore;

  const orders: PurchaseOrder[] =
    data?.purchaseOrders?.edges?.map(
      (edge: PurchaseOrderEdge) => edge.node
    ) || [];

  /*
   * IMPORTANT:
   * useVirtualizer must always be called before any
   * conditional return so React sees the same hook
   * order on every render.
   */
  const rowVirtualizer = useVirtualizer({
    count: orders.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 150,
    overscan: 5,
  });

  if (loading && !data) {
    return <Loading />;
  }

  if (error && !data) {
    return <ErrorState />;
  }

  const handleLoadMore = () => {
    const endCursor =
      data?.purchaseOrders?.pageInfo?.endCursor;

    if (!endCursor || loadingMore) {
      return;
    }

    void fetchMore({
      variables: {
        first: ORDERS_PER_PAGE,
        after: endCursor,
        status:
          filter === "All"
            ? undefined
            : filter.toLowerCase(),
        poNumber: poNumber || undefined,
        minAmount: minAmount
          ? Number(minAmount)
          : undefined,
        maxAmount: maxAmount
          ? Number(maxAmount)
          : undefined,
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

        <label>
          Start Date
          <input
            type="date"
            aria-label="Start Date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>

        <label>
          End Date
          <input
            type="date"
            aria-label="End Date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>
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
        {[
          "All",
          "Sent",
          "Acknowledged",
          "Fulfilled",
        ].map((tab) => (
          <button
            key={tab}
            className={
              filter === tab ? "active-tab" : ""
            }
            onClick={() => setFilter(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {orders.length === 0 ? (
        <EmptyState />
      ) : (
        <div
          ref={parentRef}
          role="list"
          aria-label="Purchase orders"
          style={{
            height: "600px",
            overflow: "auto",
          }}
        >
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: "100%",
              position: "relative",
            }}
          >
            {rowVirtualizer
              .getVirtualItems()
              .map((virtualItem) => {
                const order =
                  orders[virtualItem.index];

                return (
                  <div
                    key={order.po_number}
                    role="listitem"
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualItem.start}px)`,
                    }}
                  >
                    <POCard order={order} />
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {data?.purchaseOrders?.pageInfo?.hasNextPage && (
        <button
          className="load-more-btn"
          onClick={handleLoadMore}
          disabled={loadingMore}
        >
          {loadingMore
            ? "Loading..."
            : "Load More"}
        </button>
      )}
    </div>
  );
};

export default Orders;