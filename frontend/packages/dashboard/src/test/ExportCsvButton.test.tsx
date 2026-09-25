import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ExportCsvButton from "../components/export/ExportCsvButton";
import type { ShipmentStatus } from "../types/dashboard";

const shipments: ShipmentStatus = {
  total: 0,
  pending: 0,
  in_transit: 0,
  delivered: 0,
  delayed: 0,
  cancelled: 0,
} as ShipmentStatus;

describe("ExportCsvButton role access", () => {
  it("offers supplier export to the CEO", () => {
    render(
      <ExportCsvButton role="ceo" inventory={[]} suppliers={[]} shipments={shipments} />,
    );

    expect(screen.getByRole("option", { name: "Suppliers" })).toBeInTheDocument();
  });

  it("does not offer supplier export to a warehouse manager", () => {
    render(
      <ExportCsvButton
        role="warehouse_manager"
        inventory={[]}
        suppliers={[]}
        shipments={shipments}
      />,
    );

    expect(screen.queryByRole("option", { name: "Suppliers" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Inventory" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Shipments" })).toBeInTheDocument();
  });
});