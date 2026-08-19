import { useState } from "react";
import { toast } from "react-toastify";

import { useInvoice } from "../hooks/useInvoice";

import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";
import FileUpload from "../components/FileUpload";

import { colors } from "../tokens";

const Invoice = () => {
  const {
    submitInvoiceWithOfflineSupport,
    acknowledgedPOs,
    loading,
    error,
    data,
  } = useInvoice();

  const [invoiceNumber, setInvoiceNumber] =
    useState("");

  const [poReference, setPoReference] =
    useState("");

  const [amount, setAmount] =
    useState("");

  const [date, setDate] =
    useState("");

  const [file, setFile] =
    useState<File | null>(null);

  const [formError, setFormError] =
    useState("");

  const [fileError, setFileError] =
    useState("");

  const [isSubmitting, setIsSubmitting] =
    useState(false);

  // Only show the full-page loader when
  // there is no previous data.
  //
  // Because usePurchaseOrders polls, loading
  // can become true again every few seconds.
  // This prevents the form from disappearing
  // while the supplier is typing.
  if (loading && !data) {
    return <Loading />;
  }

  if (error) {
    return <ErrorState />;
  }

  const handleSubmit = async (
    e: React.FormEvent
  ) => {
    e.preventDefault();

    setFormError("");

    if (
      !invoiceNumber ||
      !poReference ||
      !amount ||
      !date ||
      !file
    ) {
      setFormError(
        "Please fill all fields."
      );
      return;
    }

    const invoiceRegex = /^INV\d+$/i;

    if (
      !invoiceRegex.test(
        invoiceNumber.trim()
      )
    ) {
      setFormError(
        "Invoice number must be like INV001."
      );
      return;
    }

    if (Number(amount) <= 0) {
      setFormError(
        "Invoice amount must be greater than 0."
      );
      return;
    }

    const today = new Date();
    const invoiceDate = new Date(date);

    if (invoiceDate > today) {
      setFormError(
        "Invoice date cannot be in the future."
      );
      return;
    }

    setIsSubmitting(true);

    try {
      const result =
        await submitInvoiceWithOfflineSupport(
          invoiceNumber.trim(),
          poReference,
          Number(amount),
          date
        );

      if (result.queued) {
        toast.info(
          "Invoice queued. It will be submitted when you are back online."
        );
      } else {
        toast.success(
          "Invoice Submitted Successfully!"
        );
      }

      setInvoiceNumber("");
      setPoReference("");
      setAmount("");
      setDate("");
      setFile(null);

      setFormError("");
      setFileError("");
    } catch (err) {
      console.error(err);

      setFormError(
        "Failed to submit invoice."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="invoice-page">
      <h2>Create Invoice</h2>

      <form onSubmit={handleSubmit}>
        {/* Invoice Number */}
        <label>Invoice Number</label>

        <input
          type="text"
          placeholder="INV001"
          value={invoiceNumber}
          onChange={(e) =>
            setInvoiceNumber(e.target.value)
          }
        />

        {/* Purchase Order */}
        <label>Purchase Order</label>

        {acknowledgedPOs.length === 0 ? (
          <div
            style={{
              marginTop: "8px",
              marginBottom: "15px",
            }}
          >
            <p>
              No acknowledged Purchase Orders
              are available for invoicing.
            </p>
          </div>
        ) : (
          <select
            value={poReference}
            onChange={(e) =>
              setPoReference(e.target.value)
            }
          >
            <option value="">
              Select Purchase Order
            </option>

            {acknowledgedPOs.map((po) => (
              <option
                key={po.po_number}
                value={po.po_number}
              >
                {po.po_number}
              </option>
            ))}
          </select>
        )}

        {/* Invoice Amount */}
        <label>Invoice Amount</label>

        <input
          type="number"
          value={amount}
          onChange={(e) =>
            setAmount(e.target.value)
          }
        />

        {/* Invoice Date */}
        <label>Invoice Date</label>

        <input
          type="date"
          value={date}
          onChange={(e) =>
            setDate(e.target.value)
          }
        />

        {/* PDF File */}
        <FileUpload
          file={file}
          setFile={setFile}
          error={fileError}
          setError={setFileError}
        />

        {/* File Error */}
        {fileError && (
          <p
            style={{
              color: colors.danger,
              marginTop: "10px",
            }}
          >
            {fileError}
          </p>
        )}

        {/* Form Error */}
        {formError && (
          <p
            style={{
              color: colors.danger,
              marginTop: "10px",
            }}
          >
            {formError}
          </p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={
            isSubmitting ||
            acknowledgedPOs.length === 0
          }
          style={{
            marginTop: "20px",
          }}
        >
          {isSubmitting
            ? "Submitting..."
            : "Submit Invoice"}
        </button>
      </form>
    </div>
  );
};

export default Invoice;