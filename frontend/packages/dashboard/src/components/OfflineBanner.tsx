import { colors, radius, space } from "../tokens";

interface OfflineBannerProps {
  savedAt: string;
  isOnline: boolean;
  hasServerError?: boolean;
  onRetry?: () => void;
}

function OfflineBanner({ savedAt, isOnline, hasServerError = false,onRetry }: OfflineBannerProps) {
  if (isOnline && !hasServerError) {
    return null;
  }

  const time = new Date(savedAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: colors.surface,
        border: `1px solid ${colors.warning}`,
        borderRadius: radius.md,
        padding: space.sm,
        marginBottom: space.lg,
        color: colors.text,
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: space.sm,
      }}
    >
      <span>
        {isOnline
          ? `Couldn't reach the server — showing data from ${time}`
          : `Offline — showing data from ${time}`}
      </span>

      {isOnline && hasServerError && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            background: colors.primary,
            color: colors.text,
            border: "none",
            borderRadius: radius.sm,
            padding: `${space.xs}px ${space.sm}px`,
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}

export default OfflineBanner;
