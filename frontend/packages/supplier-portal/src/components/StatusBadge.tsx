import type { POStatus } from "../types/po";
import { colors } from "../tokens";

interface Props {
  status: POStatus;
}

const StatusBadge = ({ status }: Props) => {

  const getColor = () => {
    switch (status) {
      case "sent":
        return colors.warning;

      case "acknowledged":
        return colors.primary;

      case "fulfilled":
        return colors.success;

      case "cancelled":
        return colors.danger;

      default:
        return colors.textMuted;
    }
  };


  const getTextColor = () => {
    switch (status) {
      case "sent":
        return "#000000";

      default:
        return colors.text;
    }
  };


  return (
    <span
      style={{
        background: getColor(),
        padding: "4px 10px",
        borderRadius: 8,
        fontSize: 12,
        color: getTextColor(),
        fontWeight: 600,
      }}
    >
      {status.toUpperCase()}
    </span>
  );
};

export default StatusBadge;