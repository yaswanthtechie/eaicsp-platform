import { gql } from "@apollo/client";

export const ACKNOWLEDGE_PO = gql`
  mutation AcknowledgePO($po_number: String!) {
    acknowledgePurchaseOrder(po_number: $po_number) {
      po_number
      status
    }
  }
`;

export const SUBMIT_INVOICE = gql`
  mutation SubmitInvoice(
    $invoiceNumber: String!
    $poReference: String!
    $amount: Int!
    $date: String!
  ) {
    submitInvoice(
      invoiceNumber: $invoiceNumber
      poReference: $poReference
      amount: $amount
      date: $date
    ) {
      invoiceNumber
      poReference
      amount
      date
    }
  }
`;