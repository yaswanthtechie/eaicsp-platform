import {
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
} from "vitest";
import {
  MemoryRouter,
  useLocation,
} from "react-router-dom";

import Login from "./Login";
import { saveTokens } from "../auth/tokenStorage";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));

vi.mock("../auth/tokenStorage", () => ({
  saveTokens: vi.fn(),
}));

import { login } from "../api/auth";

const LocationDisplay = () => {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname}
    </div>
  );
};

const renderLogin = (initialEntry: string) => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Login />
      <LocationDisplay />
    </MemoryRouter>
  );
};

describe("Login", () => {
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

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });
  });

  it("rejects an external next URL", async () => {
    renderLogin("/login?next=https://evil.com");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });
  });

  it("rejects a protocol-relative next URL", async () => {
    renderLogin("/login?next=//evil.com");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });
  });

  it("rejects a backslash-based external next URL", async () => {
    renderLogin("/login?next=/\\evil.com");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });
  });

  it("defaults to orders when next is missing", async () => {
    renderLogin("/login");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });
  });

  it("submits valid credentials and saves tokens with Remember Me enabled", async () => {
    renderLogin("/login");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    fireEvent.click(
      screen.getByLabelText("Remember Me")
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith(
        "supplier@company.com",
        "supplier@123"
      );

      expect(saveTokens).toHaveBeenCalledWith(
        "access-token",
        "refresh-token",
        true
      );
    });
  });

  it("does not submit when the email is invalid", async () => {
    renderLogin("/login");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "invalid-email",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "supplier@123",
        },
      }
    );

    vi.mocked(login).mockClear();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    expect(login).not.toHaveBeenCalled();
  });

  it("does not submit when the password is empty", async () => {
    renderLogin("/login");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    vi.mocked(login).mockClear();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    expect(
      await screen.findByText("Password is required")
    ).toBeInTheDocument();

    expect(login).not.toHaveBeenCalled();
  });

  it("shows an error when login fails", async () => {
    vi.mocked(login).mockRejectedValueOnce(
      new Error("Invalid credentials")
    );

    renderLogin("/login");

    fireEvent.change(
      screen.getByPlaceholderText("Enter Email"),
      {
        target: {
          value: "supplier@company.com",
        },
      }
    );

    fireEvent.change(
      screen.getByPlaceholderText("Enter Password"),
      {
        target: {
          value: "wrong-password",
        },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Login",
      })
    );

    expect(
      await screen.findByText(
        "Invalid email or password"
      )
    ).toBeInTheDocument();
  });
});