import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getKpiSnapshot,
  saveKpiSnapshot,
  snapshotStorageKey,
} from "../utils/kpiSnapshot";

describe("kpiSnapshot", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("does not throw when storage is blocked or full", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("SecurityError");
    });

    expect(() =>
      saveKpiSnapshot(
        "ceo",
        [{ title: "SKUs", value: 1 }],
        "2026-10-01T10:42:00.000Z",
      ),
    ).not.toThrow();

    expect(getKpiSnapshot("ceo")).toBeNull();
  });

  it("ignores a saved value with the wrong shape", () => {
    localStorage.setItem(
      snapshotStorageKey("ceo"),
      JSON.stringify({
        kpis: "not-an-array",
        savedAt: "2026-10-01T10:42:00.000Z",
      }),
    );

    expect(getKpiSnapshot("ceo")).toBeNull();
  });

  it("round-trips a valid snapshot", () => {
    const kpis = [{ title: "SKUs", value: 3 }];

    saveKpiSnapshot(
      "ceo",
      kpis,
      "2026-10-01T10:42:00.000Z",
    );

    expect(getKpiSnapshot("ceo")).toEqual({
      kpis,
      savedAt: "2026-10-01T10:42:00.000Z",
    });
  });
});