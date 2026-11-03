import { describe, expect, it } from "vitest";
import { mergeAlert } from "../utils/mergeAlert";
import type { AlertMessage } from "../types/forecast";

const eta = (id: string, predictedAt: string): AlertMessage => ({
  id, type: "shipment-eta-update", severity: "info", message: id,
  timestamp: predictedAt, shipmentId: "SHP-2026-000077", predictedAt,
});

describe("mergeAlert", () => {
  it("replaces the card when a newer prediction arrives", () => {
    const out = mergeAlert([eta("a", "2026-10-15T06:00:00Z")], eta("b", "2026-10-15T07:00:00Z"));
    expect(out.map((a) => a.id)).toEqual(["b"]);
  });

  it("ignores an older prediction for the same shipment", () => {
    const prev = [eta("b", "2026-10-15T07:00:00Z")];
    expect(mergeAlert(prev, eta("a", "2026-10-15T06:00:00Z"))).toBe(prev);
  });
});