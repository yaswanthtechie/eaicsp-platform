import { describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
} from "@testing-library/react";

import FileUpload from "./FileUpload";

describe("FileUpload", () => {
  const renderFileUpload = (
    file: File | null = null,
    error = ""
  ) => {
    const setFile = vi.fn();
    const setError = vi.fn();

    render(
      <FileUpload
        file={file}
        setFile={setFile}
        error={error}
        setError={setError}
      />
    );

    return { setFile, setError };
  };

  const getFileInput = () => {
    return document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
  };

  it("renders the upload area", () => {
    renderFileUpload();

    expect(
      screen.getByText("Drag & Drop PDF Here")
    ).toBeInTheDocument();

    expect(
      screen.getByText("or Click to Upload")
    ).toBeInTheDocument();
  });

  it("accepts a valid PDF file", () => {
    const { setFile, setError } =
      renderFileUpload();

    const file = new File(
      ["PDF content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    const fileInput = getFileInput();

    fireEvent.change(fileInput, {
      target: {
        files: [file],
      },
    });

    expect(setError).toHaveBeenCalledWith("");
    expect(setFile).toHaveBeenCalledWith(file);
  });

  it("rejects a non-PDF file", () => {
    const { setFile, setError } =
      renderFileUpload();

    const file = new File(
      ["text content"],
      "invoice.txt",
      {
        type: "text/plain",
      }
    );

    const fileInput = getFileInput();

    fireEvent.change(fileInput, {
      target: {
        files: [file],
      },
    });

    expect(setFile).toHaveBeenCalledWith(null);

    expect(setError).toHaveBeenCalledWith(
      "Only PDF files are allowed."
    );
  });

  it("rejects files larger than 10MB", () => {
    const { setFile, setError } =
      renderFileUpload();

    const largeFile = new File(
      ["large file"],
      "large.pdf",
      {
        type: "application/pdf",
      }
    );

    Object.defineProperty(largeFile, "size", {
      value: 11 * 1024 * 1024,
    });

    const fileInput = getFileInput();

    fireEvent.change(fileInput, {
      target: {
        files: [largeFile],
      },
    });

    expect(setFile).toHaveBeenCalledWith(null);

    expect(setError).toHaveBeenCalledWith(
      "Maximum file size is 10MB."
    );
  });

  it("shows the selected file", () => {
    const file = new File(
      ["PDF content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    renderFileUpload(file);

    expect(
      screen.getByText("invoice.pdf")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Preview PDF")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Remove")
    ).toBeInTheDocument();
  });

  it("removes the selected file", () => {
    const file = new File(
      ["PDF content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    const { setFile, setError } =
      renderFileUpload(file);

    fireEvent.click(
      screen.getByText("Remove")
    );

    expect(setFile).toHaveBeenCalledWith(null);
    expect(setError).toHaveBeenCalledWith("");
  });

  it("displays an error message", () => {
    renderFileUpload(
      null,
      "Only PDF files are allowed."
    );

    expect(
      screen.getByText(
        "Only PDF files are allowed."
      )
    ).toBeInTheDocument();
  });
});