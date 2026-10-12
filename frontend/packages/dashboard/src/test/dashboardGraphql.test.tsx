import type { MockLink } from "@apollo/client/testing";
import { MockedProvider } from "@apollo/client/testing/react";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useDashboardData } from "../api/dashboardGraphql";
import { GET_DASHBOARD } from "../graphql/queries";

const dashboard = {
  __typename: "Dashboard",
  kpis: {
    __typename: "KPIs",
    totalSkus: 1,
    totalUnits: 10,
    reorderItems: 0,
    alerts: 0,
  },
  inventory: [
    {
      __typename: "InventoryItem",
      sku_id: "SKU001",
      product_name: "Apples",
      category: "Food",
      warehouse_id: "WH001",
      quantity_on_hand: 10,
      reorder_point: 5,
      needs_reorder: false,
      avg_daily_demand: 1,
    },
  ],
  forecast: [],
  forecastAccuracy: [],
  inventoryHealth: [],
  supplierRisk: [],
  shipmentStatus: {
    __typename: "ShipmentStatus",
    total: 0,
    pending: 0,
    delivered: 0,
    in_transit: 0,
    delayed: 0,
    cancelled: 0,
  },
};

function wrapperWith(mocks: ReadonlyArray<MockLink.MockedResponse>) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <MockedProvider mocks={mocks}>{children}</MockedProvider>;
  };
}

describe("useDashboardData (Apollo)", () => {
  it("starts loading, then returns the dashboard data", async () => {
    const { result } = renderHook(() => useDashboardData(), {
      wrapper: wrapperWith([
        {
          request: {
            query: GET_DASHBOARD,
          },
          result: {
            data: {
              dashboard,
            },
          },
        },
      ]),
    });

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeUndefined();
    expect(result.current.data?.dashboard.inventory[0].sku_id).toBe("SKU001");
  });

  it("exposes a network error", async () => {
    const { result } = renderHook(() => useDashboardData(), {
      wrapper: wrapperWith([
        {
          request: {
            query: GET_DASHBOARD,
          },
          error: new Error("Network down"),
        },
      ]),
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error?.message).toContain("Network down");
    expect(result.current.data).toBeUndefined();
  });
});