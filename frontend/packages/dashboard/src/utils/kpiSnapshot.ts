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

  localStorage.setItem(snapshotStorageKey(scope), JSON.stringify(snapshot));

  // Remove the old shared key from earlier builds so it can't leak.
  localStorage.removeItem(STORAGE_PREFIX);
}

export function getKpiSnapshot(scope: string): KpiSnapshot | null {
  const stored = localStorage.getItem(snapshotStorageKey(scope));

  if (!stored) {
    return null;
  }

  try {
    const snapshot: unknown = JSON.parse(stored);

    if (
      typeof snapshot !== "object" ||
      snapshot === null ||
      !("kpis" in snapshot) ||
      !("savedAt" in snapshot)
    ) {
      return null;
    }

    return snapshot as KpiSnapshot;
  } catch {
    return null;
  }
}