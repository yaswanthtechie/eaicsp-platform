import { gql } from "@apollo/client";
import apolloClient from "../graphql/apollo";

export interface SubmitInvoiceInput {
  invoiceNumber: string;
  poReference: string;
  amount: number;
  date: string;
}

export interface SubmitInvoiceResponse {
  submitInvoice: {
    invoiceNumber: string;
    poReference: string;
    amount: number;
    date: string;
  };
}

const SUBMIT_INVOICE = gql`
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

export async function submitInvoice(
  input: SubmitInvoiceInput
) {
  const result =
    await apolloClient.mutate<SubmitInvoiceResponse>({
      mutation: SUBMIT_INVOICE,
      variables: {
        invoiceNumber: input.invoiceNumber,
        poReference: input.poReference,
        amount: Math.round(input.amount),
        date: input.date,
      },
    });

  if (!result.data?.submitInvoice) {
    throw new Error("Failed to submit invoice.");
  }

  return result.data.submitInvoice;
}