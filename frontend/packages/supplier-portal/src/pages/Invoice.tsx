
import { useState } from "react";
import {
  useForm,
  type SubmitHandler,
} from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "react-toastify";

import { useInvoice } from "../hooks/useInvoice";
import FileUpload from "../components/FileUpload";
import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";

const invoiceSchema = z.object({
  invoiceNumber: z
    .string()
    .trim()
    .min(1, "Invoice number is required.")
    .regex(
      /^INV\d+$/,
      "Invoice number must be like INV001."
    ),

  poReference: z
    .string()
    .min(1, "Please select a Purchase Order."),

  amount: z
    .number({
      error: "Invoice amount is required.",
    })
    .positive(
      "Invoice amount must be greater than 0."
    ),

  date: z
    .string()
    .min(1, "Invoice date is required.")
    .refine(
      (value) => {
        if (!value) {
          return false;
        }

        const today = new Date();

        const selectedDate = new Date(
          `${value}T00:00:00`
        );

        today.setHours(0, 0, 0, 0);

        return selectedDate <= today;
      },
      {
        message:
          "Invoice date cannot be in the future.",
      }
    ),
});

type InvoiceFormValues =
  z.infer<typeof invoiceSchema>;

const Invoice = () => {
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  const [fileError, setFileError] =
    useState("");

  const [submissionError, setSubmissionError] =
    useState("");

  const {
    submitInvoiceWithOfflineSupport,
    acknowledgedPOs,
    loading,
    error,
  } = useInvoice();

  const {
    register,
    handleSubmit,
    reset,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<InvoiceFormValues>({
    resolver: zodResolver(invoiceSchema),

    defaultValues: {
      invoiceNumber: "",
      poReference: "",
      amount: undefined,
      date: "",
    },
  });

  const purchaseOrders =
    acknowledgedPOs ?? [];

  const handleFileChange = (
    file: File | null
  ) => {
    setSelectedFile(file);
    setFileError("");
    setSubmissionError("");
  };

  const onSubmit: SubmitHandler<
    InvoiceFormValues
  > = async (values) => {
    setFileError("");
    setSubmissionError("");

    if (!selectedFile) {
      setFileError(
        "Please upload the invoice PDF."
      );
      return;
    }

    if (
      selectedFile.type !==
      "application/pdf"
    ) {
      setFileError(
        "Only PDF files are allowed."
      );
      return;
    }

    if (
      selectedFile.size >
      10 * 1024 * 1024
    ) {
      setFileError(
        "PDF file must be smaller than 10 MB."
      );
      return;
    }

    try {
      const result =
        await submitInvoiceWithOfflineSupport(
          values.invoiceNumber,
          values.poReference,
          values.amount,
          values.date
        );

      if (result?.queued) {
        toast.success(
          "Invoice saved offline and will be submitted when you are online."
        );
      } else {
        toast.success(
          "Invoice submitted successfully."
        );
      }

      reset();

      setSelectedFile(null);
      setFileError("");
      setSubmissionError("");
    } catch (submitError) {
      console.error(submitError);

      setSubmissionError(
        "Failed to submit invoice."
      );

      toast.error(
        "Failed to submit invoice."
      );
    }
  };

  if (loading) {
    return (
      <main className="invoice-page">
        <h2>Create Invoice</h2>
        <Loading />
      </main>
    );
  }

  if (error) {
    return (
      <main className="invoice-page">
        <h2>Create Invoice</h2>
        <ErrorState />
      </main>
    );
  }

  if (purchaseOrders.length === 0) {
    return (
      <main className="invoice-page">
        <h2>Create Invoice</h2>

        <EmptyState />

        <p
          style={{
            marginTop: "10px",
            textAlign: "center",
          }}
        >
          No acknowledged Purchase Orders are
          available for invoicing.
        </p>

        <button
          type="button"
          disabled
          style={{
            width: "100%",
            marginTop: "20px",
          }}
        >
          Submit Invoice
        </button>
      </main>
    );
  }

  return (
    <main className="invoice-page">
      <h2>Create Invoice</h2>

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <div>
          <label htmlFor="invoiceNumber">
            Invoice Number
          </label>

          <input
            id="invoiceNumber"
            type="text"
            placeholder="INV001"
            {...register("invoiceNumber")}
            aria-invalid={
              errors.invoiceNumber
                ? "true"
                : "false"
            }
            aria-describedby={
              errors.invoiceNumber
                ? "invoice-number-error"
                : undefined
            }
          />

          {errors.invoiceNumber && (
            <p
              id="invoice-number-error"
              className="error"
              role="alert"
            >
              {errors.invoiceNumber.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="poReference">
            Purchase Order
          </label>

          <select
            id="poReference"
            {...register("poReference")}
            aria-invalid={
              errors.poReference
                ? "true"
                : "false"
            }
            aria-describedby={
              errors.poReference
                ? "po-reference-error"
                : undefined
            }
          >
            <option value="">
              Select Purchase Order
            </option>

            {purchaseOrders.map((po) => (
              <option
                key={po.poNumber}
                value={po.poNumber}
              >
                {po.poNumber}
              </option>
            ))}
          </select>

          {errors.poReference && (
            <p
              id="po-reference-error"
              className="error"
              role="alert"
            >
              {errors.poReference.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="amount">
            Invoice Amount
          </label>

          <input
            id="amount"
            type="number"
            min="0"
            step="0.01"
            {...register("amount", {
              valueAsNumber: true,
            })}
            aria-invalid={
              errors.amount
                ? "true"
                : "false"
            }
            aria-describedby={
              errors.amount
                ? "amount-error"
                : undefined
            }
          />

          {errors.amount && (
            <p
              id="amount-error"
              className="error"
              role="alert"
            >
              {errors.amount.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="date">
            Invoice Date
          </label>

          <input
            id="date"
            type="date"
            {...register("date")}
            aria-invalid={
              errors.date
                ? "true"
                : "false"
            }
            aria-describedby={
              errors.date
                ? "date-error"
                : undefined
            }
          />

          {errors.date && (
            <p
              id="date-error"
              className="error"
              role="alert"
            >
              {errors.date.message}
            </p>
          )}
        </div>

        <div>
          <FileUpload
            file={selectedFile}
            setFile={handleFileChange}
            error={fileError}
            setError={setFileError}
          />

          {fileError && (
            <p
              role="alert"
              style={{
                color: "rgb(239, 68, 68)",
                marginTop: "10px",
              }}
            >
              {fileError}
            </p>
          )}
        </div>

        {submissionError && (
          <p
            role="alert"
            style={{
              color: "rgb(239, 68, 68)",
              marginTop: "10px",
            }}
          >
            {submissionError}
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            marginTop: "20px",
          }}
        >
          {isSubmitting
            ? "Submitting..."
            : "Submit Invoice"}
        </button>
      </form>
    </main>
  );
};

export default Invoice;