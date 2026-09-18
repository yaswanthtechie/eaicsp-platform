import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import Documents from "./Documents";

describe("Documents", () => {
  it("renders the documents page", async () => {
    render(<Documents />);

    expect(
      screen.getByRole("heading", {
        name: "Documents",
        level: 1,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Upload and manage supplier documents securely.",
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", {
        name: "Company Registration.pdf",
      }),
    ).toBeInTheDocument();
  });

  it("renders existing uploaded documents", async () => {
    render(<Documents />);

    expect(
      await screen.findByRole("heading", {
        name: "Company Registration.pdf",
      }),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", {
        name: "Tax Certificate.pdf",
      }),
    ).toBeInTheDocument();
  });

  it("renders the document upload controls", () => {
    render(<Documents />);

    expect(
      screen.getByRole("heading", {
        name: "Upload Document",
        level: 2,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Document Type"),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Upload PDF document"),
    ).toBeInTheDocument();
  });

  it("renders all document type options", () => {
    render(<Documents />);

    const select =
      screen.getByLabelText("Document Type");

    expect(select).toHaveValue(
      "Company Document",
    );

    expect(
      screen.getByRole("option", {
        name: "Company Document",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Tax Document",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Bank Document",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "Compliance Document",
      }),
    ).toBeInTheDocument();
  });

  it("allows changing the document type", async () => {
    const user = userEvent.setup();

    render(<Documents />);

    const select =
      screen.getByLabelText("Document Type");

    await user.selectOptions(
      select,
      "Tax Document",
    );

    expect(select).toHaveValue(
      "Tax Document",
    );
  });

  it("renders the hidden PDF file input", () => {
    render(<Documents />);

    const input =
      screen.getByLabelText(
        "Upload PDF document",
      );

    expect(input).toBeInTheDocument();

    const fileInput =
      document.getElementById(
        "document-file",
      ) as HTMLInputElement;

    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveAttribute(
      "type",
      "file",
    );
    expect(fileInput).toHaveAttribute(
      "accept",
      "application/pdf",
    );
  });

it("supports keyboard focus on the upload drop zone", async () => {
  const user = userEvent.setup();

  render(<Documents />);

  const dropZone =
    screen.getByLabelText(
      "Upload PDF document",
    );

  expect(dropZone).toHaveAttribute(
    "tabindex",
    "0",
  );

  await user.tab();
  await user.tab();

  expect(dropZone).toHaveFocus();
});

  it("renders uploaded document statuses", async () => {
    render(<Documents />);

    const statuses =
      await screen.findAllByText(
        "UPLOADED",
      );

    expect(statuses).toHaveLength(2);
  });

  it("renders uploaded document dates", async () => {
    render(<Documents />);

    expect(
      await screen.findByText(
        /Uploaded:\s*2026-09-10/,
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByText(
        /Uploaded:\s*2026-09-11/,
      ),
    ).toBeInTheDocument();
  });

  it("accepts a valid PDF file", async () => {
    const user = userEvent.setup();

    render(<Documents />);

    const fileInput =
      document.getElementById(
        "document-file",
      ) as HTMLInputElement;

    const file = new File(
      ["test pdf content"],
      "test-document.pdf",
      {
        type: "application/pdf",
      },
    );

    await user.upload(
      fileInput,
      file,
    );

    expect(
      await screen.findByText(
        "test-document.pdf uploaded successfully.",
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByRole("heading", {
        name: "test-document.pdf",
      }),
    ).toBeInTheDocument();
  });
});