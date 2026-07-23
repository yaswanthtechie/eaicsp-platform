import { gql } from "@apollo/client";

export const ACKNOWLEDGE_PO = gql`
mutation AcknowledgePO($po_number: String!) {

acknowledgePurchaseOrder(
po_number:$po_number
){

po_number

status

}

}
`; 