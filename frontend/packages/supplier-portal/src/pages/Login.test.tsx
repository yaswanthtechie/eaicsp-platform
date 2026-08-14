import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import Login from "./Login";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));

vi.mock("../auth/tokenStorage", () => ({
  saveTokens: vi.fn(),
}));

import { login } from "../api/auth";

const LocationDisplay = () => {
  const location = useLocation();

  return <div data-testid="location">{location.pathname}</div>;
};

const renderLogin = (initialEntry: string) => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Login />
      <LocationDisplay />
    </MemoryRouter>
  );
};

describe("Login next redirect security", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(login).mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
    });
  });

  it("allows a valid internal next path", async () => {
    renderLogin("/login?next=/orders");

    fireEvent.change(screen.getByPlaceholderText("Enter Email"), {
      target: { value: "supplier@company.com" },
    });

    fireEvent.change(screen.getByPlaceholderText("Enter Password"), {
      target: { value: "sup123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/orders");
    });
  });

  it("rejects an external next URL", async () => {
    renderLogin("/login?next=https://evil.com");

    fireEvent.change(screen.getByPlaceholderText("Enter Email"), {
      target: { value: "supplier@company.com" },
    });

    fireEvent.change(screen.getByPlaceholderText("Enter Password"), {
      target: { value: "sup123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/orders");
    });
  });

  it("rejects a protocol-relative next URL", async () => {
    renderLogin("/login?next=//evil.com");

    fireEvent.change(screen.getByPlaceholderText("Enter Email"), {
      target: { value: "supplier@company.com" },
    });

    fireEvent.change(screen.getByPlaceholderText("Enter Password"), {
      target: { value: "sup123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/orders");
    });
  });

  it("defaults to orders when next is missing", async () => {
    renderLogin("/login");

    fireEvent.change(screen.getByPlaceholderText("Enter Email"), {
      target: { value: "supplier@company.com" },
    });

    fireEvent.change(screen.getByPlaceholderText("Enter Password"), {
      target: { value: "sup123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/orders");
    });
  });
});