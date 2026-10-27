import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { colors, radius, space } from "../tokens";
import { fetchKpiDashboard, mapKpiResponse, type AnalyticsKpi, type KpiQueryFilters } from "../api/kpis";
import Skeleton from "./Skeleton";

const SNAPSHOT_KEY = "analytics-kpi-snapshot:v1";

type KpiPanelState = "error" | "empty" | null;

function readSnapshot(): AnalyticsKpi[] | null {
  try {
    const raw = localStorage.getItem(SNAPSHOT_KEY);
    if (!raw) return null;

    const data: unknown = JSON.parse(raw);
    if (!Array.isArray(data)) return null;

    const valid = data.every(
      (item: unknown) =>
        typeof item === "object" &&
        item !== null &&
        "title" in item &&
        typeof item.title === "string" &&
        "value" in item &&
        typeof item.value === "number" &&
        "format" in item &&
        (item.format === "percent" || item.format === "number"),
    );

    return valid ? (data as AnalyticsKpi[]) : null;
  } catch {
    // Ignore unavailable or invalid browser storage.
    return null;
  }
}

function saveSnapshot(kpis: AnalyticsKpi[]) {
  try {
    localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(kpis));
  } catch {
    // Display live data even when storage is unavailable.
  }
}

function formatValue(kpi: AnalyticsKpi) {
  return kpi.format === "percent"
    ? `${kpi.value}%`
    : new Intl.NumberFormat("en-US").format(kpi.value);
}

function getStatusColor(status?: string): string {
  switch (status) {
    case "on_target":
    case "normal":
      return colors.success;

    case "warning":
      return colors.warning;

    case "critical":
      return colors.danger;

    default:
      return colors.text;
  }
}

interface AnalyticsKpiPanelProps {
  filters?: KpiQueryFilters;
}

export default function AnalyticsKpiPanel({ filters }: AnalyticsKpiPanelProps = {}) {
  const [kpis, setKpis] = useState<AnalyticsKpi[] | null>(null);
  const [state, setState] = useState<KpiPanelState>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [showingSnapshot, setShowingSnapshot] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  const loadKpis = useCallback(async (refresh = false) => {
    if (refresh) {
      setIsLoading(true);
      setState(null);
      setErrorMessage("");
      setShowingSnapshot(false);
    }

    try {
      const response = await fetchKpiDashboard(filters);
      const data = mapKpiResponse(response);
      setLastRefreshedAt(new Date().toLocaleTimeString());
      setKpis(data);

      setState(data.length === 0 ? "empty" : null);
      setShowingSnapshot(false);

      if (data.length > 0) {
        saveSnapshot(data);
      }
    } catch (error: unknown) {
      const snapshot = readSnapshot();

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to load analytics KPIs.",
      );
      setKpis(snapshot);
      setShowingSnapshot(snapshot !== null && snapshot.length > 0);
      setState("error");
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialKpis() {
      try {
        const response = await fetchKpiDashboard(filters);
        if (cancelled) return;

        const data = mapKpiResponse(response);
        setKpis(data);
        setState(data.length === 0 ? "empty" : null);

        if (data.length > 0) {
          saveSnapshot(data);
        }
      } catch (error: unknown) {
        if (cancelled) return;

        const snapshot = readSnapshot();

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Unable to load analytics KPIs.",
        );
        setKpis(snapshot);
        setShowingSnapshot(snapshot !== null && snapshot.length > 0);
        setState("error");
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialKpis();

    return () => {
      cancelled = true;
    };
  }, [filters]);

  const hasKpis = kpis !== null && kpis.length > 0;

  return (
    <section
      aria-labelledby="analytics-kpi-heading"
      style={{ padding: 0, marginBottom: space.lg }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: space.md,
          marginBottom: space.md,
        }}
      >
        <div>
          <h2
            id="analytics-kpi-heading"
            style={{
              color: colors.text,
              marginTop: 0,
              marginBottom: space.sm,
            }}
          >
            Supply Chain Performance
          </h2>
          <p style={{ color: colors.textMuted, margin: 0 }}>
            Analytics KPIs from the Gateway
          </p>

          {lastRefreshedAt && (
            <p role="status" style={{ color: colors.textMuted, fontSize: 12 }}>
                Last refreshed: {lastRefreshedAt}
            </p>
            )}
        </div>

        <Button
          type="button"
          variant="outline"
          size="lg"
          onClick={() => void loadKpis(true)}
          disabled={isLoading}
          aria-label="Refresh analytics KPIs"
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {isLoading && !hasKpis && (
        <div
          aria-busy="true"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: space.md,
          }}
        >
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              style={{
                padding: space.lg,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
              }}
            >
              <Skeleton width="65%" height={16} />
              <div style={{ marginTop: space.md }}>
                <Skeleton width="45%" height={32} />
              </div>
            </div>
          ))}
        </div>
      )}

      {state === "error" && (
        <div
          role="alert"
          style={{
            color: colors.danger,
            padding: space.lg,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
          }}
        >
          <p>
            {showingSnapshot
              ? "KPI service unavailable. Showing the last saved values."
              : errorMessage}
          </p>
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => void loadKpis(true)}
            disabled={isLoading}
          >
            Retry
          </Button>
        </div>
      )}

      {!isLoading && state === "empty" && !hasKpis && (
        <p role="status" style={{ color: colors.textMuted }}>
          No analytics KPI data available.
        </p>
      )}

      {hasKpis && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: space.md,
          }}
        >
          {kpis.map((kpi) => (
            <article
              key={kpi.title}
              tabIndex={0}
              aria-label={`${kpi.title}: ${formatValue(kpi)}`}
              style={{
                padding: space.lg,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
                background: colors.surface,
              }}
            >
              <p
                style={{
                  color: colors.textMuted,
                  marginTop: 0,
                  marginBottom: space.sm,
                  textAlign: "center",
                }}
              >
                {kpi.title}
              </p>
              <p
                style={{
                  color: getStatusColor(kpi.status),
                  fontSize: 28,
                  fontWeight: 600,
                  margin: 0,
                  textAlign: "center",
                }}
              >
                {formatValue(kpi)}
              </p>
              {showingSnapshot && (
                <p style={{ color: colors.textMuted, fontSize: 12 }}>
                  Last saved value
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}