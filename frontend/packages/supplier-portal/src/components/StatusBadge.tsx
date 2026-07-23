import type { POStatus } from "../types/po";

interface Props {
  status: POStatus;
}

const StatusBadge = ({ status }: Props) => {
  const getColor = () => {
    switch (status) {
      case "sent":
        return "#F59E0B";

      case "acknowledged":
        return "#3B82F6";

      case "fulfilled":
        return "#10B981";

      case "cancelled":
        return "#EF4444";

      default:
        return "#8B95A8";
    }
  };

  return (
    <span
      style={{
        background: getColor(),
        padding: "4px 10px",
        borderRadius: 8,
        fontSize: 12,
        color: "#fff",
      }}
    >
      {status.toUpperCase()}
    </span>
  );
};

export default StatusBadge;