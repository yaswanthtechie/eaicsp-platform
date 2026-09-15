import { beforeEach, describe, expect, it, vi } from "vitest";

import { createNewPONotification } from "./mockNotifications";

describe("createNewPONotification", () => {
  beforeEach(() => {
    vi.spyOn(crypto, "randomUUID").mockReturnValue(
      "11111111-1111-1111-1111-111111111111"
    );

    vi.spyOn(Date, "now").mockReturnValue(123456789);
  });

  it("creates a new PO notification", () => {
    const notification =
      createNewPONotification("PO-1005");

    expect(notification).toEqual({
      id: "11111111-1111-1111-1111-111111111111",
      type: "NEW_PO",
      title: "New Purchase Order",
      message: "PO-1005 has been received.",
      poNumber: "PO-1005",
      createdAt: 123456789,
      read: false,
    });
  });

  it("creates notifications for different purchase orders", () => {
    const first =
      createNewPONotification("PO-1005");

    const second =
      createNewPONotification("PO-1006");

    expect(first.poNumber).toBe("PO-1005");
    expect(second.poNumber).toBe("PO-1006");
  });
});

