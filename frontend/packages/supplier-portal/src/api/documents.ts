export type DocumentStatus =
  | "UPLOADED"
  | "PENDING"
  | "REJECTED";

export interface SupplierDocument {
  id: string;
  name: string;
  type: string;
  uploadedAt: string;
  status: DocumentStatus;
}

const documents: SupplierDocument[] = [
  {
    id: "DOC-001",
    name: "Company Registration.pdf",
    type: "Company Document",
    uploadedAt: "2026-09-10",
    status: "UPLOADED",
  },
  {
    id: "DOC-002",
    name: "Tax Certificate.pdf",
    type: "Tax Document",
    uploadedAt: "2026-09-11",
    status: "UPLOADED",
  },
];

export const getDocuments = async (): Promise<
  SupplierDocument[]
> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(documents);
    }, 300);
  });
};
