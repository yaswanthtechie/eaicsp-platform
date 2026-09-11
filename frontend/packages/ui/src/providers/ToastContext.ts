import { createContext } from "react";

export type ToastVariant =
  | "success"
  | "error"
  | "warning"
  | "info";

export interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration?: number;
}

export interface ShowToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

export interface ToastContextValue {
  toasts: ToastItem[];
  showToast: (
    options: ShowToastOptions
  ) => void;
  removeToast: (id: number) => void;
}

export const ToastContext = createContext<
  ToastContextValue | undefined
>(undefined);