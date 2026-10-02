import { colors, radius, space } from "../tokens";

interface OfflineBannerProps {
  savedAt: string;
  isOnline: boolean;
  hasServerError?: boolean;
}

function OfflineBanner({ savedAt, isOnline, hasServerError = false }: OfflineBannerProps) {
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
      }}
    >
      {isOnline
        ? `Couldn't reach the server — showing data from ${time}`
        : `Offline — showing data from ${time}`}
    </div>
  );
}

export default OfflineBanner;
