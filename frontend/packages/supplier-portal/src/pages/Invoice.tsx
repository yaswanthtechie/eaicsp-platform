import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client";
import { toast } from "react-toastify";

import { GET_PURCHASE_ORDERS } from "../graphql/queries";
import { SUBMIT_INVOICE } from "../graphql/mutations";

import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";
import FileUpload from "../components/FileUpload";

import type { PurchaseOrder } from "../types/po";

type PurchaseOrderEdge = {
  cursor: string;
  node: PurchaseOrder;
};

const Invoice = () => {
  const { data, loading, error } = useQuery(GET_PURCHASE_ORDERS, {
    variables: {
      first: 20,
      after: null,
      status: null,
      poNumber: null,
      minAmount: null,
      maxAmount: null,
      startDate: null,
      endDate: null,
    },
  });

  const [submitInvoice] = useMutation(SUBMIT_INVOICE);

  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [poReference, setPoReference] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");

  const [file, setFile] = useState<File | null>(null);

  const [formError, setFormError] = useState("");
  const [fileError, setFileError] = useState("");

  const [uploadProgress, setUploadProgress] = useState(0);

  if (loading) return <Loading />;

  if (error) return <ErrorState />;

  const orders: PurchaseOrder[] =
    data?.purchaseOrders?.edges?.map(
      (edge: PurchaseOrderEdge) => edge.node
    ) || [];

  const acknowledgedPOs = orders.filter(
    (po) => po.status === "acknowledged"
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setFormError("");

    if (
      !invoiceNumber ||
      !poReference ||
      !amount ||
      !date ||
      !file
    ) {
      setFormError("Please fill all fields.");
      return;
    }

    const invoiceRegex = /^INV\d+$/i;

    if (!invoiceRegex.test(invoiceNumber.trim())) {
      setFormError("Invoice number must be like INV001.");
      return;
    }

    if (Number(amount) <= 0) {
      setFormError("Invoice amount must be greater than 0.");
      return;
    }

    const today = new Date();
    const invoiceDate = new Date(date);

    if (invoiceDate > today) {
      setFormError("Invoice date cannot be in the future.");
      return;
    }

    setUploadProgress(0);

    const timer = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) {
          clearInterval(timer);
          return 90;
        }

        return prev + 10;
      });
    }, 200);

    try {
      await submitInvoice({
        variables: {
          invoiceNumber,
          poReference,
          amount: Number(amount),
          date,
        },
      });

      clearInterval(timer);
      setUploadProgress(100);

      toast.success("Invoice Submitted Successfully!");

      setInvoiceNumber("");
      setPoReference("");
      setAmount("");
      setDate("");
      setFile(null);

      setFormError("");
      setFileError("");

      setTimeout(() => {
        setUploadProgress(0);
      }, 1500);

    } catch (err) {
      clearInterval(timer);
      setUploadProgress(0);

      console.error(err);

      setFormError("Failed to submit invoice.");
    }
  };

  return (
    <div className="invoice-page">
      <h2>Create Invoice</h2>

      <form onSubmit={handleSubmit}>
        <label>Invoice Number</label>

        <input
          type="text"
          placeholder="INV001"
          value={invoiceNumber}
          onChange={(e) => setInvoiceNumber(e.target.value)}
        />

        <label>Purchase Order</label>

        <select
          value={poReference}
          onChange={(e) => setPoReference(e.target.value)}
        >
          <option value="">Select Purchase Order</option>

          {acknowledgedPOs.map((po) => (
            <option
              key={po.po_number}
              value={po.po_number}
            >
              {po.po_number}
            </option>
          ))}
        </select>

        <label>Invoice Amount</label>

        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />

        <label>Invoice Date</label>

        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

        <FileUpload
          file={file}
          setFile={setFile}
          error={fileError}
          setError={setFileError}
        />

        {uploadProgress > 0 && (
          <div style={{ marginTop: "15px" }}>
            <progress
              value={uploadProgress}
              max={100}
              style={{ width: "100%" }}
            />
            <p>{uploadProgress}% Uploaded</p>
          </div>
        )}

        {fileError && (
          <p
            style={{
              color: "red",
              marginTop: "10px",
            }}
          >
            {fileError}
          </p>
        )}

        {formError && (
          <p
            style={{
              color: "red",
              marginTop: "10px",
            }}
          >
            {formError}
          </p>
        )}

        <button
          type="submit"
          style={{ marginTop: "20px" }}
        >
          Submit Invoice
        </button>
      </form>
    </div>
  );
};

export default Invoice;