import { Badge } from "./Badge";

export type Status =
  | "online"
  | "offline"
  | "pending"
  | "success"
  | "warning"
  | "error";

export interface StatusIndicatorProps {
  status: Status;
  label?: string;
}

export function StatusIndicator({
  status,
  label,
}: StatusIndicatorProps) {
  const badgeStatus =
    status === "online" || status === "success"
      ? "success"
      : status === "pending" || status === "warning"
      ? "warning"
      : status === "offline" || status === "error"
      ? "danger"
      : "neutral";

  const text = label ?? status;

  return <Badge status={badgeStatus}>{text}</Badge>;
}