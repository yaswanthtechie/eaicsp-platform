import { describe, expect, it } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import Documents from "./Documents";

describe("Documents", () => {
  it("renders the documents page", () => {
    render(<Documents />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Documents",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Upload and manage supplier documents securely."
      )
    ).toBeInTheDocument();
  });

  it("renders existing uploaded documents", () => {
    render(<Documents />);

    expect(
      screen.getByRole("heading", {
        name: "Company Registration.pdf",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "Tax Certificate.pdf",
      })
    ).toBeInTheDocument();
  });

  it("renders the document upload controls", () => {
    render(<Documents />);

    expect(
      screen.getByRole("heading", {
        name: "Upload Document",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Document Type")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Upload PDF document",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText("Drop a PDF here")
    ).toBeInTheDocument();

    expect(
      screen.getByText("or press Enter to choose a file")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Maximum file size: 5 MB")
    ).toBeInTheDocument();
  });

  it("renders all document type options", () => {
    render(<Documents />);

    const select = screen.getByLabelText("Document Type");

    expect(select).toHaveValue("Company Document");

    expect(
      screen.getByRole("option", {
        name: "Company Document",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Tax Document",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Bank Document",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Compliance Document",
      })
    ).toBeInTheDocument();
  });

  it("allows changing the document type", () => {
    render(<Documents />);

    const select = screen.getByLabelText("Document Type");

    fireEvent.change(select, {
      target: {
        value: "Tax Document",
      },
    });

    expect(select).toHaveValue("Tax Document");
  });

  it("renders the hidden PDF file input", () => {
    render(<Documents />);

    const fileInput = document.querySelector(
      "#document-file"
    ) as HTMLInputElement;

    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveAttribute(
      "type",
      "file"
    );
    expect(fileInput).toHaveAttribute(
      "accept",
      "application/pdf"
    );
  });

  it("supports keyboard focus on the upload drop zone", () => {
    render(<Documents />);

    const dropZone = screen.getByRole("button", {
      name: "Upload PDF document",
    });

    expect(dropZone).toHaveAttribute("tabindex", "0");

    dropZone.focus();

    expect(dropZone).toHaveFocus();
  });

  it("renders uploaded document statuses", () => {
    render(<Documents />);

    const statuses = screen.getAllByText("UPLOADED");

    expect(statuses).toHaveLength(2);
  });

  it("renders uploaded document dates", () => {
    render(<Documents />);

    expect(
      screen.getByText(/Uploaded:\s*2026-09-10/)
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Uploaded:\s*2026-09-11/)
    ).toBeInTheDocument();
  });

  it("accepts a valid PDF file", async () => {
    render(<Documents />);

    const fileInput = document.querySelector(
      "#document-file"
    ) as HTMLInputElement;

    const file = new File(
      ["PDF test content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    fireEvent.change(fileInput, {
      target: {
        files: [file],
      },
    });

    await waitFor(() => {
      expect(
        screen.getByText("invoice.pdf")
      ).toBeInTheDocument();
    });
  });
});