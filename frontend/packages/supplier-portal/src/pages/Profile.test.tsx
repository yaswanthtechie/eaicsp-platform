import { describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import Profile from "./Profile";

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("Profile", () => {
  it("renders the profile and settings page", () => {
    render(<Profile />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /profile & settings/i,
      })
    ).toBeInTheDocument();
  });

  it("renders the profile fields with default values", () => {
    render(<Profile />);

    expect(
      screen.getByLabelText("Company Name")
    ).toHaveValue("ABC Supplies Pvt Ltd");

    expect(
      screen.getByLabelText("Contact Name")
    ).toHaveValue("Supplier Admin");

    expect(
      screen.getByLabelText("Email")
    ).toHaveValue("supplier@company.com");

    expect(
      screen.getByLabelText("Phone Number")
    ).toHaveValue("9876543210");
  });

  it("renders the notifications setting", () => {
    render(<Profile />);

    const checkbox = screen.getByRole("checkbox", {
      name: /enable notifications/i,
    });

    expect(checkbox).toBeChecked();
  });

  it("renders the save button", () => {
    render(<Profile />);

    expect(
      screen.getByRole("button", {
        name: /save changes/i,
      })
    ).toBeInTheDocument();
  });

  it("shows validation errors for invalid required fields", async () => {
    render(<Profile />);

    fireEvent.change(
      screen.getByLabelText("Company Name"),
      {
        target: { value: "" },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Contact Name"),
      {
        target: { value: "A" },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Email"),
      {
        target: { value: "invalid-email" },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Phone Number"),
      {
        target: { value: "123" },
      }
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      })
    );

    await waitFor(() => {
      expect(
        screen.getByText("Company name is required.")
      ).toBeInTheDocument();

      expect(
        screen.getByText(
          "Contact name must be at least 2 characters."
        )
      ).toBeInTheDocument();

      expect(
        screen.getByText("Enter a valid email address.")
      ).toBeInTheDocument();

      expect(
        screen.getByText(
          "Phone number must be at least 10 digits."
        )
      ).toBeInTheDocument();
    });
  });

  it("allows changing profile values", () => {
    render(<Profile />);

    const companyName = screen.getByLabelText(
      "Company Name"
    );

    fireEvent.change(companyName, {
      target: {
        value: "New Supplier Company",
      },
    });

    expect(companyName).toHaveValue(
      "New Supplier Company"
    );
  });

  it("allows toggling notifications", () => {
    render(<Profile />);

    const checkbox = screen.getByRole("checkbox", {
      name: /enable notifications/i,
    });

    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);

    expect(checkbox).not.toBeChecked();
  });

  it("shows saving state when submitting valid data", async () => {
    render(<Profile />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /save changes/i,
      })
    );

    expect(
      screen.getByRole("button", {
        name: /saving/i,
      })
    ).toBeDisabled();

    await waitFor(
      () => {
        expect(
          screen.getByRole("button", {
            name: /save changes/i,
          })
        ).not.toBeDisabled();
      },
      {
        timeout: 1500,
      }
    );
  });
});