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


  return (
    <>
      <div
        className={`drop-zone ${
          isDragging ? "drag-active" : ""
        }`}
        onDragEnter={() => setIsDragging(true)}
        onDragLeave={(e) => {
  e.preventDefault();
  setIsDragging(false);
}}
        onDragOver={(e) => {
  e.preventDefault();
  setIsDragging(true);
}}
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
            {formatFileSize(file.size)}
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
        <p className="error">
          {error}
        </p>
      )}

    </>
  );
};

export default FileUpload;