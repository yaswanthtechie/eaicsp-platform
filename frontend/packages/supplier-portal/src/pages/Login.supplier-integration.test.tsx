import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import {
  MemoryRouter,
} from "react-router-dom";

import Login from "./Login";

import { login } from "../api/auth";

import {
  clearTokens,
  getSupplierId,
} from "../auth/tokenStorage";


vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));


const mockedLogin = vi.mocked(login);


describe("Login → supplier identity integration", () => {
  afterEach(() => {
    cleanup();
    clearTokens();
    vi.clearAllMocks();
  });


  it("persists the supplier ID returned by login", async () => {
    mockedLogin.mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
      supplier_id: "SUP001",
    });


    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );


    fireEvent.change(
      screen.getByLabelText("Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      },
    );


    fireEvent.change(
      screen.getByLabelText("Password"),
      {
        target: {
          value: "password123",
        },
      },
    );


    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      }),
    );


    await waitFor(() => {
      expect(mockedLogin).toHaveBeenCalledWith(
        "supplier@company.com",
        "password123",
      );
    });


    await waitFor(() => {
      expect(getSupplierId()).toBe("SUP001");
    });
  });
});