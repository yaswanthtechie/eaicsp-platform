export interface KpiSnapshot {
  kpis: Array<{
    title: string;
    value: number;
  }>;
  savedAt: string;
}

const STORAGE_PREFIX = "executive-kpi-snapshot";

// One snapshot per role (and warehouse, for warehouse managers), so one
// user's numbers are never shown to another user on the same device.
export function snapshotStorageKey(scope: string): string {
  return `${STORAGE_PREFIX}:${scope}`;
}

export function saveKpiSnapshot(
  scope: string,
  kpis: KpiSnapshot["kpis"],
  savedAt: string,
): void {
  const snapshot: KpiSnapshot = { kpis, savedAt };

  try {
    localStorage.setItem(snapshotStorageKey(scope), JSON.stringify(snapshot));

    // Remove the old shared key from earlier builds so it can't leak.
    localStorage.removeItem(STORAGE_PREFIX);
  } catch {
    // Storage blocked or full (private mode, quota). The dashboard still
    // works; only the offline snapshot is skipped.
  }
}

export function getKpiSnapshot(scope: string): KpiSnapshot | null {
  try {
    const stored = localStorage.getItem(snapshotStorageKey(scope));

    if (!stored) {
      return null;
    }

    const snapshot: unknown = JSON.parse(stored);

    return isKpiSnapshot(snapshot) ? snapshot : null;
  } catch {
    return null;
  }
}

function isKpiSnapshot(value: unknown): value is KpiSnapshot {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.savedAt === "string" &&
    Array.isArray(candidate.kpis) &&
    candidate.kpis.every((kpi: unknown) => {
      if (typeof kpi !== "object" || kpi === null) {
        return false;
      }

      const entry = kpi as Record<string, unknown>;

      return typeof entry.title === "string" && typeof entry.value === "number";
    })
  );
}