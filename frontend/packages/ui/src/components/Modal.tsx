import React, { useEffect } from "react";
import { colors, space, radius } from "../tokens";

export interface ModalProps {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}

export function Modal({
  open,
  title,
  children,
  onClose,
}: ModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: colors.overlay,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        style={{
          backgroundColor: colors.surface,
          color: colors.text,
          padding: space.lg,
          borderRadius: radius.md,
          width: "100%",
          maxWidth: 400,
          border: `1px solid ${colors.border}`,
          boxShadow: colors.shadow,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: space.md,
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 20,
            }}
          >
            {title}
          </h2>

          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: 18,
              color: colors.text,
            }}
          >
            ✕
          </button>
        </div>

        <div>{children}</div>
      </div>
    </div>
  );
}