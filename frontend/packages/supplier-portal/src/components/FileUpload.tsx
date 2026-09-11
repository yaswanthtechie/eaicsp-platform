import { useRef, useState } from "react";

interface Props {
  file: File | null;
  setFile: (file: File | null) => void;
  error: string;
  setError: (error: string) => void;
}

const FileUpload = ({
  file,
  setFile,
  error,
  setError,
}: Props) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);

  const validateFile = (selected: File) => {
    if (selected.type !== "application/pdf") {
      setFile(null);
      setError("Only PDF files are allowed.");
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
      setFile(null);
      setError("Maximum file size is 10MB.");
      return;
    }

    setError("");
    setFile(selected);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const selected = e.target.files?.[0];

    if (selected) {
      validateFile(selected);
    }

    e.target.value = "";
  };

  const handleDrop = (
    e: React.DragEvent<HTMLDivElement>
  ) => {
    e.preventDefault();

    setIsDragging(false);

    const selected = e.dataTransfer.files[0];

    if (selected) {
      validateFile(selected);
    }
  };

  const formatFileSize = (size: number) => {
    const kb = size / 1024;

    if (kb > 1024) {
      return `${(kb / 1024).toFixed(2)} MB`;
    }

    return `${kb.toFixed(2)} KB`;
  };

  const handleRemove = () => {
    setFile(null);
    setError("");

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const handlePreview = () => {
    if (!file) return;

    const url = URL.createObjectURL(file);
    window.open(url, "_blank");

    URL.revokeObjectURL(url);
  };

  const handleBrowseFiles = () => {
    inputRef.current?.click();
  };

  return (
    <>
      <div
        className={`upload-box ${
          isDragging ? "dragging" : ""
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <p>Drag & Drop PDF Here</p>

        <p>or</p>

        <button
          type="button"
          onClick={handleBrowseFiles}
        >
          Browse files
        </button>

        <input
          id="invoice-file"
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          hidden
          onChange={handleChange}
        />
      </div>

      {file && (
        <div className="file-preview">
          <p>{file.name}</p>

          <p>{formatFileSize(file.size)}</p>

          <button
            type="button"
            onClick={handlePreview}
          >
            Preview PDF
          </button>

          <button
            type="button"
            onClick={handleRemove}
          >
            Remove
          </button>
        </div>
      )}

      {error && (
        <p className="error">
          {error}
        </p>
      )}
    </>
  );
};

export default FileUpload;