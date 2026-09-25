import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  useForm,
  type SubmitHandler,
} from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import {
  getDocuments,
  type SupplierDocument,
} from "../api/documents";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

const documentSchema = z.object({
  documentType: z
    .string()
    .min(1, "Document type is required."),

  file: z
    .custom<File | undefined>(
      (value) =>
        value === undefined ||
        (value instanceof File &&
          value.type === "application/pdf"),
      {
        message: "Only PDF files are allowed.",
      },
    )
    .refine(
      (file) =>
        file === undefined ||
        file.size <= MAX_FILE_SIZE,
      {
        message: "File size must be 5 MB or less.",
      },
    ),
});

type DocumentFormData = z.infer<
  typeof documentSchema
>;

export default function Documents() {
  const inputRef =
    useRef<HTMLInputElement>(null);

  const [documents, setDocuments] =
    useState<SupplierDocument[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [loadError, setLoadError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    reset,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<DocumentFormData>({
    resolver: zodResolver(documentSchema),

    defaultValues: {
      documentType: "Company Document",
      file: undefined,
    },
  });

  const fileRegister = register("file");

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
    if (!isSubmitting) {
      inputRef.current?.click();
    }
  };

  const onSubmit: SubmitHandler<
    DocumentFormData
  > = async (data) => {
    const file = data.file;

    if (!file) {
      setError("file", {
        type: "required",
        message: "Please select a PDF file.",
      });

      return;
    }

    setSuccess("");

    await new Promise<void>((resolve) => {
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

          const newDocument: SupplierDocument =
            {
              id: `DOC-${String(
                nextNumber,
              ).padStart(3, "0")}`,

              name: file.name,

              type: data.documentType,

              uploadedAt:
                new Date()
                  .toISOString()
                  .slice(0, 10),

              status: "UPLOADED",
            };

          return [
            newDocument,
            ...current,
          ];
        });

        setSuccess(
          `${file.name} uploaded successfully.`,
        );

        if (inputRef.current) {
          inputRef.current.value = "";
        }

        reset({
          documentType:
            data.documentType,
          file: undefined,
        });

        resolve();
      }, 600);
    });
  };

  const processFile = (file: File | undefined) => {
    setSuccess("");
    clearErrors("file");

    setValue("file", file, {
      shouldValidate: true,
      shouldDirty: true,
    });

    if (!file) {
      return;
    }

    /*
     * Automatically submit the form after
     * the file has been selected or dropped.
     *
     * React Hook Form + Zod performs the
     * validation before onSubmit runs.
     */
    void handleSubmit(onSubmit)();
  };

  const handleInputChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    processFile(
      event.target.files?.[0],
    );
  };

  const handleDrop = (
    event: React.DragEvent<HTMLDivElement>,
  ) => {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    processFile(
      event.dataTransfer.files?.[0],
    );
  };

  return (
    <main className="documents-page">
      <header className="page-header">
        <h1>Documents</h1>

        <p>
          Upload and manage supplier
          documents securely.
        </p>
      </header>

      <section
        className="document-upload-card"
        aria-labelledby="upload-heading"
      >
        <h2 id="upload-heading">
          Upload Document
        </h2>

        <form
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <label htmlFor="document-type">
            Document Type
          </label>

          <select
            id="document-type"
            {...register("documentType")}
            aria-invalid={Boolean(
              errors.documentType,
            )}
          >
            <option>
              Company Document
            </option>

            <option>
              Tax Document
            </option>

            <option>
              Bank Document
            </option>

            <option>
              Compliance Document
            </option>
          </select>

          {errors.documentType && (
            <p
              className="error"
              role="alert"
            >
              {
                errors.documentType
                  .message
              }
            </p>
          )}

          <input
            {...fileRegister}
            ref={(element) => {
              fileRegister.ref(element);
              inputRef.current = element;
            }}
            id="document-file"
            type="file"
            accept="application/pdf"
            onChange={
              handleInputChange
            }
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
            onDragOver={(event) =>
              event.preventDefault()
            }
            onDrop={handleDrop}
            aria-label="Upload PDF document"
          >
            <strong>
              Drop a PDF here
            </strong>

            <span>
              or press Enter to choose
              a file
            </span>

            <small>
              Maximum file size: 5 MB
            </small>
          </div>

          {errors.file && (
            <p
              className="error"
              role="alert"
            >
              {errors.file.message}
            </p>
          )}

          {success && (
            <p
              className="document-success"
              role="status"
            >
              {success}
            </p>
          )}

          {isSubmitting && (
            <p
              className="document-uploading"
              role="status"
            >
              Uploading document...
            </p>
          )}
        </form>
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
          <div
            className="error-state"
            role="alert"
          >
            {loadError}
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <h3>No documents</h3>

            <p>
              No supplier documents have
              been uploaded yet.
            </p>
          </div>
        ) : (
          <div className="document-list">
            {documents.map(
              (document) => (
                <article
                  className="document-card"
                  key={document.id}
                >
                  <div>
                    <h3>
                      {document.name}
                    </h3>

                    <p>
                      {document.type}
                    </p>

                    <p>
                      Uploaded:{" "}
                      {document.uploadedAt}
                    </p>
                  </div>

                  <span className="document-status">
                    {document.status}
                  </span>
                </article>
              ),
            )}
          </div>
        )}
      </section>
    </main>
  );
}
