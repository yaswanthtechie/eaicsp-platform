import {
  useEffect,
  useRef,
  useId,
  type MouseEvent,
  type ReactNode,
} from "react";

export interface ModalProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  closeOnOverlayClick?: boolean;
}

export function Modal({
  isOpen,
  title,
  children,
  onClose,
  footer,
  closeOnOverlayClick = true,
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
const previouslyFocused = useRef<HTMLElement | null>(null);
const titleId = useId();

  useEffect(() => {
  if (!isOpen) {
    return;
  }

  previouslyFocused.current =
    document.activeElement as HTMLElement;

  dialogRef.current?.focus();

  const FOCUSABLE =
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      onClose();
      return;
    }

    if (event.key !== "Tab") {
      return;
    }

    const nodes =
      dialogRef.current?.querySelectorAll<HTMLElement>(
        FOCUSABLE
      );

    if (!nodes || nodes.length === 0) {
      return;
    }

    const first = nodes[0];
    const last = nodes[nodes.length - 1];

    if (
      event.shiftKey &&
      document.activeElement === first
    ) {
      event.preventDefault();
      last.focus();
    } else if (
      !event.shiftKey &&
      document.activeElement === last
    ) {
      event.preventDefault();
      first.focus();
    }
  };

  window.addEventListener(
    "keydown",
    handleKeyDown
  );

  return () => {
    window.removeEventListener(
      "keydown",
      handleKeyDown
    );

    previouslyFocused.current?.focus();
  };
}, [isOpen, onClose]);

  

  const handleOverlayClick = () => {
    if (closeOnOverlayClick) {
      onClose();
    }
  };

  const handleDialogClick = (event: MouseEvent<HTMLDivElement>) => {
    event.stopPropagation();
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="modal-overlay"
      onClick={handleOverlayClick}
    >
    <div
  ref={dialogRef}
  className="modal"
  role="dialog"
  aria-modal="true"
  aria-labelledby={titleId}
  tabIndex={-1}
  onClick={handleDialogClick}
>
  <div className="modal-header">
    <h2 id={titleId} className="modal-title">
      {title}
    </h2>

          <button
            type="button"
            className="modal-close"
            aria-label="Close modal"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {children}
        </div>

        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}