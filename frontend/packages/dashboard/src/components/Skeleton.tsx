
import { colors, radius } from "../tokens";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
}

export default function Skeleton({
  width = "100%",
  height = 20,
  borderRadius = radius.sm,
}: SkeletonProps) {
  return (
    <div
      style={{
        width,
        height,
        background: colors.border,
        borderRadius,
        animation: "skeleton-loading 1.5s ease-in-out infinite",
      }}
    />
  );
}

