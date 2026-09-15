import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Invoice from "./Invoice";

const mockSubmitInvoiceWithOfflineSupport = vi.fn();

let mockAcknowledgedPOs = [
  {
    poNumber: "PO1004",
    supplierId: "SUP003",
    status: "ACKNOWLEDGED",
    totalAmount: 21000,
    expectedDelivery: "2026-08-10",
    items: [],
  },
  {
    poNumber: "PO1005",
    supplierId: "SUP004",
    status: "ACKNOWLEDGED",
    totalAmount: 14500,
    expectedDelivery: "2026-08-15",
    items: [],
  },
];

vi.mock("../hooks/useInvoice", () => ({
  useInvoice: () => ({
    submitInvoiceWithOfflineSupport:
      mockSubmitInvoiceWithOfflineSupport,

    acknowledgedPOs: mockAcknowledgedPOs,

    loading: false,

    error: null,

    data: {
      purchaseOrders: {
        edges: [],
        pageInfo: {
          hasNextPage: false,
          endCursor: null,
        },
      },
    },
  }),
}));

vi.mock("../components/FileUpload", () => ({
  default: ({
    file,
    setFile,
  }: {
    file: File | null;
    setFile: (file: File | null) => void;
    error: string;
    setError: (error: string) => void;
  }) => (
    <div>
      <label htmlFor="invoice-file">
        Invoice PDF
      </label>

      <input
        id="invoice-file"
        type="file"
        accept="application/pdf"
        onChange={(event) => {
          const selectedFile =
            event.target.files?.[0] ?? null;

          setFile(selectedFile);
        }}
      />

      {file && (
        <span data-testid="selected-file">
          {file.name}
        </span>
      )}
    </div>
  ),
}));

vi.mock("../components/Loading", () => ({
  default: () => (
    <div role="status">
      Loading...
    </div>
  ),
}));

vi.mock("../components/ErrorState", () => ({
  default: () => (
    <div role="alert">
      Something went wrong.
    </div>
  ),
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}));

describe("Invoice", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockAcknowledgedPOs = [
      {
        poNumber: "PO1004",
        supplierId: "SUP003",
        status: "ACKNOWLEDGED",
        totalAmount: 21000,
        expectedDelivery: "2026-08-10",
        items: [],
      },
      {
        poNumber: "PO1005",
        supplierId: "SUP004",
        status: "ACKNOWLEDGED",
        totalAmount: 14500,
        expectedDelivery: "2026-08-15",
        items: [],
      },
    ];

    mockSubmitInvoiceWithOfflineSupport.mockResolvedValue({
      queued: false,
    });
  });

  const renderInvoice = () => {
    render(<Invoice />);
  };

  const fillValidForm = async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.type(
      screen.getByLabelText("Invoice Number"),
      "INV001"
    );

    await user.selectOptions(
      screen.getByLabelText("Purchase Order"),
      "PO1004"
    );

    await user.type(
      screen.getByLabelText("Invoice Amount"),
      "20000"
    );

    await user.type(
      screen.getByLabelText("Invoice Date"),
      "2026-09-10"
    );

    const file = new File(
      ["invoice pdf content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    await user.upload(
      screen.getByLabelText("Invoice PDF"),
      file
    );

    return user;
  };

  it("renders the Create Invoice page", () => {
    renderInvoice();

    expect(
      screen.getByRole("heading", {
        name: "Create Invoice",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Invoice Number")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Purchase Order")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Invoice Amount")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Invoice Date")
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText("Invoice PDF")
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    ).toBeInTheDocument();
  });

  it("renders acknowledged purchase orders", () => {
    renderInvoice();

    expect(
      screen.getByRole("option", {
        name: "PO1004",
      })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("option", {
        name: "PO1005",
      })
    ).toBeInTheDocument();
  });

  it("shows validation errors when required fields are empty", async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByText(
        "Invoice number is required."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Please select a Purchase Order."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Invoice amount is required."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Invoice date is required."
      )
    ).toBeInTheDocument();

    expect(
      mockSubmitInvoiceWithOfflineSupport
    ).not.toHaveBeenCalled();
  });

  it("validates the invoice number format", async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.type(
      screen.getByLabelText("Invoice Number"),
      "ABC123"
    );

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByText(
        "Invoice number must be like INV001."
      )
    ).toBeInTheDocument();

    expect(
      mockSubmitInvoiceWithOfflineSupport
    ).not.toHaveBeenCalled();
  });

  it("validates that invoice amount is greater than zero", async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.type(
      screen.getByLabelText("Invoice Number"),
      "INV001"
    );

    await user.selectOptions(
      screen.getByLabelText("Purchase Order"),
      "PO1004"
    );

    await user.type(
      screen.getByLabelText("Invoice Amount"),
      "0"
    );

    await user.type(
      screen.getByLabelText("Invoice Date"),
      "2026-09-10"
    );

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByText(
        "Invoice amount must be greater than 0."
      )
    ).toBeInTheDocument();

    expect(
      mockSubmitInvoiceWithOfflineSupport
    ).not.toHaveBeenCalled();
  });

  it("does not allow a future invoice date", async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.type(
      screen.getByLabelText("Invoice Number"),
      "INV001"
    );

    await user.selectOptions(
      screen.getByLabelText("Purchase Order"),
      "PO1004"
    );

    await user.type(
      screen.getByLabelText("Invoice Amount"),
      "20000"
    );

    await user.type(
      screen.getByLabelText("Invoice Date"),
      "2099-12-31"
    );

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByText(
        "Invoice date cannot be in the future."
      )
    ).toBeInTheDocument();

    expect(
      mockSubmitInvoiceWithOfflineSupport
    ).not.toHaveBeenCalled();
  });

  it("requires a PDF file before submitting", async () => {
    const user = userEvent.setup();

    renderInvoice();

    await user.type(
      screen.getByLabelText("Invoice Number"),
      "INV001"
    );

    await user.selectOptions(
      screen.getByLabelText("Purchase Order"),
      "PO1004"
    );

    await user.type(
      screen.getByLabelText("Invoice Amount"),
      "20000"
    );

    await user.type(
      screen.getByLabelText("Invoice Date"),
      "2026-09-10"
    );

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByText(
        "Please upload the invoice PDF."
      )
    ).toBeInTheDocument();

    expect(
      mockSubmitInvoiceWithOfflineSupport
    ).not.toHaveBeenCalled();
  });

  it("allows selecting a PDF file", async () => {
    const user = userEvent.setup();

    renderInvoice();

    const file = new File(
      ["invoice pdf content"],
      "invoice.pdf",
      {
        type: "application/pdf",
      }
    );

    await user.upload(
      screen.getByLabelText("Invoice PDF"),
      file
    );

    expect(
      screen.getByTestId("selected-file")
    ).toHaveTextContent("invoice.pdf");
  });

  it("submits a valid invoice successfully", async () => {
    const user = await fillValidForm();

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    await waitFor(() => {
      expect(
        mockSubmitInvoiceWithOfflineSupport
      ).toHaveBeenCalledWith(
        "INV001",
        "PO1004",
        20000,
        "2026-09-10"
      );
    });
  });

  it("queues the invoice when offline", async () => {
    mockSubmitInvoiceWithOfflineSupport.mockResolvedValueOnce({
      queued: true,
    });

    const user = await fillValidForm();

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    await waitFor(() => {
      expect(
        mockSubmitInvoiceWithOfflineSupport
      ).toHaveBeenCalledWith(
        "INV001",
        "PO1004",
        20000,
        "2026-09-10"
      );
    });
  });

  it("shows submitting state while the invoice is being submitted", async () => {
    let resolveSubmission:
      | ((value: { queued: boolean }) => void)
      | undefined;

    mockSubmitInvoiceWithOfflineSupport.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSubmission = resolve;
      })
    );

    const user = await fillValidForm();

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    expect(
      await screen.findByRole("button", {
        name: "Submitting...",
      })
    ).toBeDisabled();

    resolveSubmission?.({
      queued: false,
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: "Submit Invoice",
        })
      ).toBeInTheDocument();
    });
  });

  it("handles submission failure", async () => {
    mockSubmitInvoiceWithOfflineSupport.mockRejectedValueOnce(
      new Error("Submission failed")
    );

    const user = await fillValidForm();

    await user.click(
      screen.getByRole("button", {
        name: "Submit Invoice",
      })
    );

    await waitFor(() => {
      expect(
        mockSubmitInvoiceWithOfflineSupport
      ).toHaveBeenCalledWith(
        "INV001",
        "PO1004",
        20000,
        "2026-09-10"
      );
    });

    expect(
      await screen.findByText(
        "Failed to submit invoice."
      )
    ).toBeInTheDocument();
  });

  it("disables submission when there are no acknowledged purchase orders", () => {
    mockAcknowledgedPOs = [];

    renderInvoice();

    const submitButton =
      screen.getByRole("button", {
        name: "Submit Invoice",
      });

    expect(submitButton).toBeDisabled();

    expect(
      screen.getByText(
        "No acknowledged Purchase Orders are available for invoicing."
      )
    ).toBeInTheDocument();
  });
});