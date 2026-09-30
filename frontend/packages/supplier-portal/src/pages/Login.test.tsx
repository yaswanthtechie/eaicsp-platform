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
import {
  saveTokens,
  saveSupplierId,
} from "../auth/tokenStorage";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));

vi.mock("../auth/tokenStorage", () => ({
  saveTokens: vi.fn(),
  saveSupplierId: vi.fn(),
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

const fillLoginForm = () => {
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
};

const submitLogin = () => {
  fireEvent.click(
    screen.getByRole("button", {
      name: "Login",
    })
  );
};

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(login).mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
      supplier_id: "SUP001",
    });
  });

  it("allows a valid internal next path", async () => {
    renderLogin("/login?next=/orders");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });

    expect(saveSupplierId).toHaveBeenCalledWith(
      "SUP001",
      false
    );
  });

  it("rejects an external next URL", async () => {
    renderLogin("/login?next=https://evil.com");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });

    expect(saveSupplierId).toHaveBeenCalledWith(
      "SUP001",
      false
    );
  });

  it("rejects a protocol-relative next URL", async () => {
    renderLogin("/login?next=//evil.com");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });

    expect(saveSupplierId).toHaveBeenCalledWith(
      "SUP001",
      false
    );
  });

  it("rejects a backslash-based external next URL", async () => {
    renderLogin("/login?next=/\\evil.com");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });

    expect(saveSupplierId).toHaveBeenCalledWith(
      "SUP001",
      false
    );
  });

  it("defaults to orders when next is missing", async () => {
    renderLogin("/login");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(
        screen.getByTestId("location")
      ).toHaveTextContent("/orders");
    });

    expect(saveSupplierId).toHaveBeenCalledWith(
      "SUP001",
      false
    );
  });

  it("submits valid credentials and saves tokens with Remember Me enabled", async () => {
    renderLogin("/login");

    fillLoginForm();

    fireEvent.click(
      screen.getByLabelText("Remember Me")
    );

    submitLogin();

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

      expect(saveSupplierId).toHaveBeenCalledWith(
        "SUP001",
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

    submitLogin();

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

    submitLogin();

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

    fillLoginForm();
    submitLogin();

    expect(
      await screen.findByText(
        "Invalid email or password"
      )
    ).toBeInTheDocument();

    expect(saveSupplierId).not.toHaveBeenCalled();
  });

  it("saves the supplier ID returned by login", async () => {
    renderLogin("/login");

    fillLoginForm();
    submitLogin();

    await waitFor(() => {
      expect(saveSupplierId).toHaveBeenCalledWith(
        "SUP001",
        false
      );
    });
  });
});
