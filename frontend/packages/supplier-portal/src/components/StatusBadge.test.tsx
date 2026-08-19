import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import StatusBadge from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders SENT status", () => {
    render(<StatusBadge status="sent" />);

    expect(
      screen.getByText("SENT")
    ).toBeInTheDocument();
  });

  it("renders ACKNOWLEDGED status", () => {
    render(
      <StatusBadge status="acknowledged" />
    );

    expect(
      screen.getByText("ACKNOWLEDGED")
    ).toBeInTheDocument();
  });

  it("renders FULFILLED status", () => {
    render(
      <StatusBadge status="fulfilled" />
    );

    expect(
      screen.getByText("FULFILLED")
    ).toBeInTheDocument();
  });

  it("renders CANCELLED status", () => {
    render(
      <StatusBadge status="cancelled" />
    );

    expect(
      screen.getByText("CANCELLED")
    ).toBeInTheDocument();
  });

  it("renders DRAFT status", () => {
    render(
      <StatusBadge status="draft" />
    );

    expect(
      screen.getByText("DRAFT")
    ).toBeInTheDocument();
  });

  it("applies the correct color for SENT status", () => {
    render(<StatusBadge status="sent" />);

    const badge = screen.getByText("SENT");

    expect(badge).toHaveStyle({
      background: "#F59E0B",
      color: "#000000",
    });
  });

  it("applies the correct color for ACKNOWLEDGED status", () => {
    render(
      <StatusBadge status="acknowledged" />
    );

    const badge =
      screen.getByText("ACKNOWLEDGED");

    expect(badge).toHaveStyle({
      background: "#3B82F6",
      color: "#E6EAF2",
    });
  });

  it("applies the correct color for FULFILLED status", () => {
    render(
      <StatusBadge status="fulfilled" />
    );

    const badge =
      screen.getByText("FULFILLED");

    expect(badge).toHaveStyle({
      background: "#10B981",
      color: "#E6EAF2",
    });
  });

  it("applies the correct color for CANCELLED status", () => {
    render(
      <StatusBadge status="cancelled" />
    );

    const badge =
      screen.getByText("CANCELLED");

    expect(badge).toHaveStyle({
      background: "#EF4444",
      color: "#E6EAF2",
    });
  });

  it("renders the status in uppercase", () => {
    render(
      <StatusBadge status="acknowledged" />
    );

    expect(
      screen.getByText("ACKNOWLEDGED")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("acknowledged")
    ).not.toBeInTheDocument();
  });
});