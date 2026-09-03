import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ErrorBoundary from "./ErrorBoundary";

const ThrowError = () => {
  throw new Error("Deliberate render error");
};

describe("ErrorBoundary", () => {
  it("catches a render error and shows the fallback UI", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(
      screen.getByRole("alert")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Something went wrong",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "The application encountered an unexpected error. Please try again."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Reload Application",
      })
    ).toBeInTheDocument();

    consoleError.mockRestore();
  });
});