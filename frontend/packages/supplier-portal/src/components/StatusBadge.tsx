import type { POStatus } from "../types/po";
import { colors } from "../tokens";

interface Props {
  status: POStatus;
}

const StatusBadge = ({ status }: Props) => {

  const getColor = () => {
    switch (status) {
      case "SENT":
        return colors.warning;

      case "ACKNOWLEDGED":
        return colors.primary;

      case "FULFILLED":
        return colors.success;

      case "CANCELLED":
        return colors.danger;

      default:
        return colors.textMuted;
    }
  };


  const getTextColor = () => {
    switch (status) {
      case "SENT":
        return colors.black;

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