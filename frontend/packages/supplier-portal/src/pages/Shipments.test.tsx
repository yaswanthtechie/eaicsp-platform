import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import Shipments from "./Shipments";

describe("Shipments", () => {
  it("renders the shipment tracking page", () => {
    render(<Shipments />);

    expect(
      screen.getByRole("heading", {
        name: "Shipment Tracking",
        level: 1,
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Track purchase order deliveries and shipment progress."
      )
    ).toBeInTheDocument();
  });

  it("renders the shipment list", () => {
    render(<Shipments />);

    expect(
      screen.getByRole("heading", {
        name: "Shipments",
        level: 2,
      })
    ).toBeInTheDocument();

    expect(screen.getByText("PO1001")).toBeInTheDocument();
    expect(screen.getByText("PO1002")).toBeInTheDocument();
    expect(screen.getByText("PO1003")).toBeInTheDocument();
    expect(screen.getByText("PO1004")).toBeInTheDocument();
  });

  it("renders shipment statuses", () => {
    render(<Shipments />);

    expect(screen.getByText("Processing")).toBeInTheDocument();

    expect(screen.getAllByText("In Transit")).toHaveLength(2);

    expect(
      screen.getByText("Out for Delivery")
    ).toBeInTheDocument();

    expect(screen.getAllByText("Delivered")).toHaveLength(2);
  });

  it("renders shipment summary counts", () => {
    render(<Shipments />);

    const summary = screen.getByRole("region", {
      name: "Shipment summary",
    });

    expect(summary).toHaveTextContent("Total Shipments");
    expect(summary).toHaveTextContent("4");

    expect(summary).toHaveTextContent("In Transit");
    expect(summary).toHaveTextContent("1");

    expect(summary).toHaveTextContent("Delivered");
    expect(summary).toHaveTextContent("1");
  });

  it("renders delivery progress bars", () => {
    render(<Shipments />);

    expect(
      screen.getByRole("progressbar", {
        name: "PO1001 delivery progress",
      })
    ).toHaveAttribute("aria-valuenow", "25");

    expect(
      screen.getByRole("progressbar", {
        name: "PO1002 delivery progress",
      })
    ).toHaveAttribute("aria-valuenow", "65");

    expect(
      screen.getByRole("progressbar", {
        name: "PO1003 delivery progress",
      })
    ).toHaveAttribute("aria-valuenow", "90");

    expect(
      screen.getByRole("progressbar", {
        name: "PO1004 delivery progress",
      })
    ).toHaveAttribute("aria-valuenow", "100");
  });

  it("renders shipment information", () => {
    render(<Shipments />);

    expect(screen.getByText("Laptop")).toBeInTheDocument();
    expect(screen.getByText("Monitor")).toBeInTheDocument();
    expect(screen.getByText("Keyboard")).toBeInTheDocument();
    expect(
      screen.getByText("Server Equipment")
    ).toBeInTheDocument();

    expect(screen.getByText("2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("2026-08-05")).toBeInTheDocument();
    expect(screen.getByText("2026-08-08")).toBeInTheDocument();
    expect(screen.getByText("2026-08-10")).toBeInTheDocument();
  });
});