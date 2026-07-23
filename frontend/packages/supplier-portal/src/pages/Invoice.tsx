import { useState } from "react";
import { useQuery } from "@apollo/client";

import { GET_PURCHASE_ORDERS } from "../graphql/queries";

import Loading from "../components/Loading";
import ErrorState from "../components/ErrorState";
import FileUpload from "../components/FileUpload";

const Invoice = () => {
  // GraphQL Query
  const { data, loading, error } = useQuery(GET_PURCHASE_ORDERS);

  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [poReference, setPoReference] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");

  const [file, setFile] = useState<File | null>(null);

  const [formError, setFormError] = useState("");

  if (loading) return <Loading />;

  if (error) return <ErrorState />;

  const orders = data.purchaseOrders;

  const acknowledgedPOs = orders.filter(
    (po: any) => po.status === "acknowledged"
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

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

    alert("Invoice Submitted Successfully!");

    setInvoiceNumber("");
    setPoReference("");
    setAmount("");
    setDate("");
    setFile(null);
    setFormError("");
  };

  return (
    <div className="invoice-page">

      <h2>Create Invoice</h2>

      <form onSubmit={handleSubmit}>

        <label>Invoice Number</label>

        <input
          type="text"
          value={invoiceNumber}
          onChange={(e) => setInvoiceNumber(e.target.value)}
          placeholder="INV001"
        />

        <label>Purchase Order</label>

        <select
          value={poReference}
          onChange={(e) => setPoReference(e.target.value)}
        >
          <option value="">
            Select Purchase Order
          </option>

          {acknowledgedPOs.map((po: any) => (
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
          error={formError}
          setError={setFormError}
        />

        {formError && (
          <p style={{ color: "red", marginTop: "10px" }}>
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