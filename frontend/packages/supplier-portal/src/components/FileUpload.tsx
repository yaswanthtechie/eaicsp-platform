import { useRef } from "react";

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

  const validateFile = (selected: File) => {
    if (selected.type !== "application/pdf") {
      setError("Only PDF files are allowed.");
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
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
  };

  const handleDrop = (
    e: React.DragEvent<HTMLDivElement>
  ) => {
    e.preventDefault();

    const selected = e.dataTransfer.files[0];

    if (selected) {
      validateFile(selected);
    }
  };

  return (
    <>
      <div
        className="drop-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <p>Drag & Drop PDF Here</p>

        <p>or Click to Upload</p>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          hidden
          onChange={handleChange}
        />
      </div>

      {file && (
        <div className="file-preview">
          <p>{file.name}</p>

          <p>
            {(file.size / 1024).toFixed(2)} KB
          </p>

          <button
            type="button"
            onClick={() => setFile(null)}
          >
            Remove
          </button>
        </div>
      )}

      {error && (
        <p className="error">{error}</p>
      )}
    </>
  );
};

export default FileUpload;