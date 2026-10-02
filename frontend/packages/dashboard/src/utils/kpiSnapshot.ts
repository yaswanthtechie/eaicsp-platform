export interface KpiSnapshot {
  kpis: Array<{
    title: string;
    value: number;
  }>;
  savedAt: string;
}

const STORAGE_KEY = "executive-kpi-snapshot";

export function saveKpiSnapshot(
  kpis: KpiSnapshot["kpis"],
): void {
  const snapshot: KpiSnapshot = {
    kpis,
    savedAt: new Date().toISOString(),
  };

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(snapshot),
  );
}

export function getKpiSnapshot(): KpiSnapshot | null {
  const stored = localStorage.getItem(STORAGE_KEY);

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