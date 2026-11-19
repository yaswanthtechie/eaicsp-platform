import {
  mockProductsResponse,
  mockWarehousesResponse,
} from "../mocks/inventoryResponses";
import { getAuthSession } from "./auth";

export interface InventoryProduct {
  sku_id: string;
  name: string;
  unit_of_measure?: string | null;
}

export interface InventoryWarehouse {
  warehouse_id: string;
  name: string;
}

interface InventoryListResponse<T> {
  items: T[];
  total: number;
}

export interface InventoryNameMaps {
  products: Record<string, string>;
  warehouses: Record<string, string>;
}

const PAGE_LIMIT = 1000;
const REQUEST_TIMEOUT_MS = 10000;

const USE_MOCK_INVENTORY_NAMES =
  import.meta.env.DEV &&
  import.meta.env.VITE_USE_MOCK_INVENTORY_NAMES === "true";

const EMPTY_NAME_MAPS: InventoryNameMaps = {
  products: {},
  warehouses: {},
};

let cachedAccessToken: string | null = null;
let cachedInventoryNames: Promise<InventoryNameMaps> | null = null;

async function fetchInventoryPages<T>(
  endpoint: string,
  accessToken: string,
): Promise<T[]> {
  const items: T[] = [];
  let offset = 0;
  let total = Infinity;

  while (offset < total) {
    const controller = new AbortController();

    const timeoutId = setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS,
    );

    let response: Response;

    try {
      response = await fetch(
        `${endpoint}?limit=${PAGE_LIMIT}&offset=${offset}`,
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            Accept: "application/json",
          },
          signal: controller.signal,
        },
      );
    } finally {
      clearTimeout(timeoutId);
    }

    if (!response.ok) {
      throw new Error(
        `Inventory lookup failed (HTTP ${response.status}).`,
      );
    }

    const payload: unknown = await response.json();

    if (
      typeof payload !== "object" ||
      payload === null ||
      !("items" in payload) ||
      !Array.isArray(payload.items) ||
      !("total" in payload) ||
      typeof payload.total !== "number"
    ) {
      throw new Error("Invalid inventory list response.");
    }

    const page = payload as InventoryListResponse<T>;

    if (page.items.length === 0) {
      break;
    }

    items.push(...page.items);
    total = page.total;
    offset += page.items.length;
  }

  return items;
}

export async function fetchInventoryNames(): Promise<InventoryNameMaps> {
  const session = getAuthSession();

  if (!session) {
    return EMPTY_NAME_MAPS;
  }

  const accessToken = session.access_token;

  if (
    cachedAccessToken === accessToken &&
    cachedInventoryNames
  ) {
    return cachedInventoryNames;
  }

  cachedAccessToken = accessToken;

  cachedInventoryNames = (async () => {
    // Development-only mock data. Do not call real endpoints in mock mode.
    if (USE_MOCK_INVENTORY_NAMES) {
      return {
        products: Object.fromEntries(
          mockProductsResponse.items.map((product) => [
            product.sku_id,
            product.name,
          ]),
        ),
        warehouses: Object.fromEntries(
          mockWarehousesResponse.items.map((warehouse) => [
            warehouse.warehouse_id,
            warehouse.name,
          ]),
        ),
      };
    }

    const [productsResult, warehousesResult] =
      await Promise.allSettled([
        fetchInventoryPages<InventoryProduct>(
          "/api/v1/inventory/products",
          accessToken,
        ),
        fetchInventoryPages<InventoryWarehouse>(
          "/api/v1/inventory/warehouses",
          accessToken,
        ),
      ]);

    return {
      products:
        productsResult.status === "fulfilled"
          ? Object.fromEntries(
              productsResult.value.map((product) => [
                product.sku_id,
                product.name,
              ]),
            )
          : {},

      warehouses:
        warehousesResult.status === "fulfilled"
          ? Object.fromEntries(
              warehousesResult.value.map((warehouse) => [
                warehouse.warehouse_id,
                warehouse.name,
              ]),
            )
          : {},
    };
  })();

  return cachedInventoryNames;
}

export function formatProductLabel(
  skuId: string,
  productNames: Record<string, string>,
): string {
  const name = productNames[skuId];
  return name ? `${name} (${skuId})` : skuId;
}

export function formatWarehouseLabel(
  warehouseId: string,
  warehouseNames: Record<string, string>,
): string {
  const name = warehouseNames[warehouseId];
  return name ? `${name} (${warehouseId})` : warehouseId;
}
