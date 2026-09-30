import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import StatusBadge from "./StatusBadge";
import { colors } from "../tokens";

describe("StatusBadge", () => {
  it("renders SENT status", () => {
    render(<StatusBadge status="SENT" />);

    expect(
      screen.getByText("SENT")
    ).toBeInTheDocument();
  });

  it("renders ACKNOWLEDGED status", () => {
    render(
      <StatusBadge status="ACKNOWLEDGED" />
    );

    expect(
      screen.getByText("ACKNOWLEDGED")
    ).toBeInTheDocument();
  });

  it("renders FULFILLED status", () => {
    render(
      <StatusBadge status="FULFILLED" />
    );

    expect(
      screen.getByText("FULFILLED")
    ).toBeInTheDocument();
  });

  it("renders CANCELLED status", () => {
    render(
      <StatusBadge status="CANCELLED" />
    );

    expect(
      screen.getByText("CANCELLED")
    ).toBeInTheDocument();
  });

  it("renders DRAFT status", () => {
    render(
      <StatusBadge status="DRAFT" />
    );

    expect(
      screen.getByText("DRAFT")
    ).toBeInTheDocument();
  });

  it("applies the correct color for SENT status", () => {
    render(<StatusBadge status="SENT" />);

    const badge = screen.getByText("SENT");

    expect(badge).toHaveStyle({
      background: colors.warning,
      color: colors.black,
    });
  });

  it("applies the correct color for ACKNOWLEDGED status", () => {
    render(
      <StatusBadge status="ACKNOWLEDGED" />
    );

    const badge =
      screen.getByText("ACKNOWLEDGED");

    expect(badge).toHaveStyle({
      background: colors.primary,
      color: colors.text,
    });
  });

  it("applies the correct color for FULFILLED status", () => {
    render(
      <StatusBadge status="FULFILLED" />
    );

    const badge =
      screen.getByText("FULFILLED");

    expect(badge).toHaveStyle({
      background: colors.success,
      color: colors.text,
    });
  });

  it("applies the correct color for CANCELLED status", () => {
    render(
      <StatusBadge status="CANCELLED" />
    );

    const badge =
      screen.getByText("CANCELLED");

    expect(badge).toHaveStyle({
      background: colors.danger,
      color: colors.text,
    });
  });

  it("renders the status in uppercase", () => {
    render(
      <StatusBadge status="ACKNOWLEDGED" />
    );

    expect(
      screen.getByText("ACKNOWLEDGED")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("acknowledged")
    ).not.toBeInTheDocument();
  });
});