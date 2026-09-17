import { useEffect, useRef, useState } from "react";
import {
  getDocuments,
  type SupplierDocument,
} from "../api/documents";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

export default function Documents() {
  const inputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<SupplierDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [selectedType, setSelectedType] =
    useState("Company Document");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadDocuments = async () => {
      try {
        setLoading(true);
        setLoadError("");

        const data = await getDocuments();

        if (isMounted) {
          setDocuments(data);
        }
      } catch {
        if (isMounted) {
          setLoadError(
            "Unable to load documents. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    void loadDocuments();

    return () => {
      isMounted = false;
    };
  }, []);

  const openFilePicker = () => {
    inputRef.current?.click();
  };

  const handleFile = (file: File | undefined) => {
    if (isUploading) {
      return;
    }

    setError("");
    setSuccess("");

    if (!file) {
      return;
    }

    if (file.type !== "application/pdf") {
      setError("Only PDF files are allowed.");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError("File size must be 5 MB or less.");
      return;
    }

    setIsUploading(true);
window.setTimeout(() => {
  setDocuments((current) => {
    const usedIds = new Set(
      current.map(
        (document) => document.id,
      ),
    );

    let nextNumber = 1;

    while (
      usedIds.has(
        `DOC-${String(
          nextNumber,
        ).padStart(3, "0")}`,
      )
    ) {
      nextNumber += 1;
    }

    const newDocument: SupplierDocument = {
      id: `DOC-${String(
        nextNumber,
      ).padStart(3, "0")}`,
      name: file.name,
      type: selectedType,
      uploadedAt: new Date()
        .toISOString()
        .slice(0, 10),
      status: "UPLOADED",
    };

    return [
      newDocument,
      ...current,
    ];
  });

  setIsUploading(false);

  setSuccess(
    `${file.name} uploaded successfully.`,
  );

  if (inputRef.current) {
    inputRef.current.value = "";
  }
}, 600);
  };

  const handleInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    handleFile(event.target.files?.[0]);
  };

  const handleDrop = (
    event: React.DragEvent<HTMLDivElement>,
  ) => {
    event.preventDefault();
    handleFile(event.dataTransfer.files?.[0]);
  };

  return (
    <main className="documents-page">
      <header className="page-header">
        <h1>Documents</h1>
        <p>
          Upload and manage supplier documents securely.
        </p>
      </header>

      <section
        className="document-upload-card"
        aria-labelledby="upload-heading"
      >
        <h2 id="upload-heading">Upload Document</h2>

        <label htmlFor="document-type">
          Document Type
        </label>

        <select
          id="document-type"
          value={selectedType}
          onChange={(event) =>
            setSelectedType(event.target.value)
          }
        >
          <option>Company Document</option>
          <option>Tax Document</option>
          <option>Bank Document</option>
          <option>Compliance Document</option>
        </select>

        <input
          ref={inputRef}
          id="document-file"
          type="file"
          accept="application/pdf"
          onChange={handleInputChange}
          hidden
        />

        <div
          className="document-drop-zone"
          role="button"
          tabIndex={0}
          onClick={openFilePicker}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" ||
              event.key === " "
            ) {
              event.preventDefault();
              openFilePicker();
            }
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
          aria-label="Upload PDF document"
        >
          <strong>Drop a PDF here</strong>
          <span>or press Enter to choose a file</span>
          <small>Maximum file size: 5 MB</small>
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {success && (
          <p className="document-success" role="status">
            {success}
          </p>
        )}

        {isUploading && (
          <p className="document-uploading" role="status">
            Uploading document...
          </p>
        )}
      </section>

      <section
        aria-labelledby="document-list-heading"
        className="document-list-section"
      >
        <h2 id="document-list-heading">
          Uploaded Documents
        </h2>

        {loading ? (
          <div
            className="loading-state"
            role="status"
            aria-label="Loading documents..."
          >
            Loading documents...
          </div>
        ) : loadError ? (
          <div className="error-state" role="alert">
            {loadError}
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <h3>No documents</h3>
            <p>
              No supplier documents have been uploaded yet.
            </p>
          </div>
        ) : (
          <div className="document-list">
            {documents.map((document) => (
              <article
                className="document-card"
                key={document.id}
              >
                <div>
                  <h3>{document.name}</h3>
                  <p>{document.type}</p>
                  <p>
                    Uploaded: {document.uploadedAt}
                  </p>
                </div>

                <span className="document-status">
                  {document.status}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
