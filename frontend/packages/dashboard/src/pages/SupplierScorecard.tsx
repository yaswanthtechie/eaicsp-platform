import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";

import {
  fetchSupplierScorecard,
  type SupplierScorecardRow,
} from "../api/supplierScoreCard";

import { colors, radius, space } from "../tokens";

type SortDirection = "asc" | "desc";

type SortKey =
  | "supplier_name"
  | "score"
  | "tier"
  | "on_time_delivery_percent"
  | "incident_count";

interface SortConfig {
  key: SortKey;
  direction: SortDirection;
}

const PAGE_SIZE = 10;

const TIER_ORDER: Record<string, number> = {
  Low: 1,
  Medium: 2,
  High: 3,
  Critical: 4,
};

const SORT_HEADERS: { key: SortKey; label: string }[] = [
  { key: "supplier_name", label: "Supplier" },
  { key: "score", label: "Risk score" },
  { key: "tier", label: "Risk tier" },
  { key: "on_time_delivery_percent", label: "On-time delivery" },
  { key: "incident_count", label: "Incidents (12 months)" },
];

function getIncidentCount(row: SupplierScorecardRow): number | null {
  const features = row.risk?.client_risk_features;

  if (!features) return null;

  return (
    (features.quality_incidents_12m ?? 0) +
    (features.delay_incidents_12m ?? 0) +
    (features.dispute_incidents_12m ?? 0) +
    (features.other_incidents_12m ?? 0)
  );
}

function getTierBadgeStyle(tier: string | null | undefined) {
  switch (tier) {
    case "Critical":
      return {
        color: colors.danger,
        background: colors.dangerAlpha12,
      };

    case "High":
      return {
        color: colors.warning,
        background: colors.bg,
      };

    case "Medium":
      return {
        color: colors.info,
        background: colors.bg,
      };

    case "Low":
      return {
        color: colors.success,
        background: colors.successAlpha12,
      };

    default:
      return {
        color: colors.textMuted,
        background: colors.bg,
      };
  }
}

function getScoreDisplay(score: number | null | undefined): string {
  return score == null ? "Unavailable" : score.toFixed(1);
}

const tableCellStyle: CSSProperties = {
  padding: `${space.md}px`,
  borderBottom: `1px solid ${colors.border}`,
  textAlign: "left",
  color: colors.text,
  verticalAlign: "middle",
};

const buttonStyle: CSSProperties = {
  background: colors.surface,
  color: colors.text,
  border: `1px solid ${colors.border}`,
  borderRadius: radius.md,
  padding: `${space.sm}px ${space.md}px`,
  cursor: "pointer",
  fontSize: 14,
};

export default function SupplierScorecard() {
  const [rows, setRows] = useState<SupplierScorecardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");

  const [expandedSupplier, setExpandedSupplier] = useState<string | null>(
    null,
  );

  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "score",
    direction: "desc",
  });

  const [currentPage, setCurrentPage] = useState(1);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchSupplierScorecard();
      setRows(data);
      setCurrentPage(1);
      setExpandedSupplier(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load supplier data.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const data = await fetchSupplierScorecard();

        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load supplier data.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    if (!query) return rows;

    return rows.filter(
      (row) =>
        row.supplier_name.toLowerCase().includes(query) ||
        row.supplier_id.toLowerCase().includes(query),
    );
  }, [rows, searchQuery]);

  const sortedRows = useMemo(() => {
    return [...filteredRows].sort((a, b) => {
      let valueA: string | number | null;
      let valueB: string | number | null;

      switch (sortConfig.key) {
        case "supplier_name":
          valueA = a.supplier_name;
          valueB = b.supplier_name;
          break;

        case "score":
          valueA = a.risk?.score ?? null;
          valueB = b.risk?.score ?? null;
          break;

        case "tier":
          valueA =
            a.risk?.tier == null
              ? null
              : TIER_ORDER[a.risk.tier] ?? null;
          valueB =
            b.risk?.tier == null
              ? null
              : TIER_ORDER[b.risk.tier] ?? null;
          break;

        case "on_time_delivery_percent":
          valueA = a.on_time_delivery_percent;
          valueB = b.on_time_delivery_percent;
          break;

        case "incident_count":
          valueA = getIncidentCount(a);
          valueB = getIncidentCount(b);
          break;
      }

      // Missing values always stay at the bottom.
      if (valueA == null && valueB == null) {
        return a.supplier_name.localeCompare(b.supplier_name);
      }

      if (valueA == null) return 1;
      if (valueB == null) return -1;

      let difference: number;

      if (
        sortConfig.key === "supplier_name" &&
        typeof valueA === "string" &&
        typeof valueB === "string"
      ) {
        difference = valueA.localeCompare(valueB);
      } else {
        difference = Number(valueA) - Number(valueB);
      }

      if (difference === 0) {
        return a.supplier_name.localeCompare(b.supplier_name);
      }

      return sortConfig.direction === "asc"
        ? difference
        : -difference;
    });
  }, [filteredRows, sortConfig]);

  const totalPages = Math.max(
    1,
    Math.ceil(sortedRows.length / PAGE_SIZE),
  );

  const paginatedRows = useMemo(() => {
    const startIndex = (currentPage - 1) * PAGE_SIZE;

    return sortedRows.slice(
      startIndex,
      startIndex + PAGE_SIZE,
    );
  }, [sortedRows, currentPage]);

  const handleSort = (key: SortKey) => {
    setSortConfig((current) => {
      if (current.key === key) {
        return {
          key,
          direction: current.direction === "asc" ? "desc" : "asc",
        };
      }

      return {
        key,
        direction: key === "score" ? "desc" : "asc",
      };
    });

    setCurrentPage(1);
  };

  const handleSearch = (value: string) => {
    setSearchQuery(value);
    setCurrentPage(1);
    setExpandedSupplier(null);
  };

  const handlePreviousPage = () => {
    setCurrentPage((page) => Math.max(1, page - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((page) => Math.min(totalPages, page + 1));
  };

  const handleSupplierKeyDown = (
    event: KeyboardEvent<HTMLTableRowElement>,
    supplierId: string,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();

      setExpandedSupplier((current) =>
        current === supplierId ? null : supplierId,
      );
    }
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: colors.bg,
        color: colors.text,
        padding: space.lg,
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: space.md,
          marginBottom: space.lg,
        }}
      >
        <div style={{ flex: "1 1 300px" }}>
          <h1
            style={{
              margin: 0,
              fontSize: space.xl,
              fontWeight: 700,
            }}
          >
            Supplier Risk Scorecard
          </h1>

          <p
            style={{
              color: colors.textMuted,
              marginTop: space.xs,
            }}
          >
            Supplier risk scores, delivery performance and incident history
          </p>

          <div style={{ marginTop: space.md }}>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => handleSearch(event.target.value)}
              placeholder="Search supplier name or ID..."
              aria-label="Search suppliers by name or ID"
              style={{
                width: "100%",
                maxWidth: 380,
                boxSizing: "border-box",
                padding: `${space.sm}px ${space.md}px`,
                background: colors.surface,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                borderRadius: radius.md,
                fontSize: 14,
                outline: "none",
              }}
            />

            <p
              style={{
                color: colors.textMuted,
                fontSize: 12,
                marginTop: space.xs,
              }}
            >
              Showing {sortedRows.length} of {rows.length} suppliers
            </p>
          </div>
        </div>

        <nav
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: space.sm,
          }}
        >
          <Link
            to="/"
            style={{
              ...buttonStyle,
              textDecoration: "none",
            }}
          >
            Executive Dashboard
          </Link>

          <button
            type="button"
            onClick={() => void loadData()}
            disabled={loading}
            style={{
              ...buttonStyle,
              opacity: loading ? 0.6 : 1,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            Refresh
          </button>
        </nav>
      </header>

      {/* Loading state */}
      {loading && (
        <section
          style={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.lg,
            color: colors.textMuted,
          }}
        >
          Loading supplier data...
        </section>
      )}

      {/* Error state */}
      {!loading && error && (
        <section
          role="alert"
          style={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.lg,
          }}
        >
          <p style={{ color: colors.danger }}>{error}</p>

          <button
            type="button"
            onClick={() => void loadData()}
            style={buttonStyle}
          >
            Retry
          </button>
        </section>
      )}

      {!loading && !error && sortedRows.length === 0 && (
        <section
          style={{
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            padding: space.lg,
            color: colors.textMuted,
          }}
        >
          {rows.length === 0
            ? "No suppliers found."
            : "No suppliers match your search."}
        </section>
      )}

      {!loading && !error && sortedRows.length > 0 && (
        <div
          style={{
            overflowX: "auto",
            background: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              minWidth: 850,
            }}
          >
            <thead>
              <tr>
                {SORT_HEADERS.map(({ key, label }) => {
                  const active = sortConfig.key === key;

                  return (
                    <th
                      key={key}
                      scope="col"
                      aria-sort={
                        active
                          ? sortConfig.direction === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      style={{
                        ...tableCellStyle,
                        color: colors.textMuted,
                        fontWeight: 600,
                        background: colors.surface,
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => handleSort(key)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: active ? colors.primary : colors.textMuted,
                          fontWeight: 600,
                          fontSize: 13,
                          cursor: "pointer",
                          padding: 0,
                        }}
                      >
                        {label}{" "}
                        {active
                          ? sortConfig.direction === "asc"
                            ? "↑"
                            : "↓"
                          : "↕"}
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>

            <tbody>
              {paginatedRows.map((row) => {
                const isExpanded =
                  expandedSupplier === row.supplier_id;

                const tier = row.risk?.tier;
                const incidentCount = getIncidentCount(row);

                return (
                  <Fragment key={row.supplier_id}>
                    <tr
                      tabIndex={0}
                      aria-expanded={isExpanded}
                      aria-label={`Show risk reasons for ${row.supplier_name}`}
                      onClick={() =>
                        setExpandedSupplier(
                          isExpanded ? null : row.supplier_id,
                        )
                      }
                      onKeyDown={(event) =>
                        handleSupplierKeyDown(event, row.supplier_id)
                      }
                      style={{
                        cursor: "pointer",
                      }}
                    >
                      <td style={tableCellStyle}>
                        <strong>{row.supplier_name}</strong>

                        <div
                          style={{
                            color: colors.textMuted,
                            fontSize: 12,
                            marginTop: space.xs,
                          }}
                        >
                          {row.supplier_id}
                        </div>
                      </td>

                      <td style={tableCellStyle}>
                        {getScoreDisplay(row.risk?.score)}
                      </td>

                      <td style={tableCellStyle}>
                        <span
                          style={{
                            ...getTierBadgeStyle(tier),
                            display: "inline-block",
                            padding: `${space.xs}px ${space.sm + 2}px`,
                            borderRadius: radius.md,
                            fontSize: 12,
                            fontWeight: 600,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {tier ?? "Unavailable"}
                        </span>
                      </td>

                      <td style={tableCellStyle}>
                        {row.on_time_delivery_percent == null
                          ? "Not tracked"
                          : `${row.on_time_delivery_percent.toFixed(1)}%`}
                      </td>

                      <td style={tableCellStyle}>
                        {incidentCount == null
                          ? "Unavailable"
                          : incidentCount}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td
                          colSpan={5}
                          style={{
                            ...tableCellStyle,
                            background: colors.bg,
                            padding: space.lg,
                          }}
                        >
                          <h3
                            style={{
                              marginTop: 0,
                              fontSize: 15,
                            }}
                          >
                            Top risk reasons
                          </h3>

                          {row.risk?.top_reasons?.length ? (
                            <ol
                              style={{
                                paddingLeft: space.lg,
                                lineHeight: 1.8,
                              }}
                            >
                              {row.risk.top_reasons
                                .slice(0, 3)
                                .map((reason, index) => (
                                  <li key={`${index}-${reason}`}>
                                    {reason}
                                  </li>
                                ))}
                            </ol>
                          ) : (
                            <p style={{ color: colors.textMuted }}>
                              {row.risk_error ??
                                "No risk reasons available."}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: space.md,
              padding: space.md,
              borderTop: `1px solid ${colors.border}`,
            }}
          >
            <span
              style={{
                color: colors.textMuted,
                fontSize: 13,
              }}
            >
              Page {currentPage} of {totalPages} · {sortedRows.length} suppliers
            </span>

            <div
              style={{
                display: "flex",
                gap: space.sm,
              }}
            >
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={handlePreviousPage}
                style={{
                  ...buttonStyle,
                  opacity: currentPage === 1 ? 0.5 : 1,
                  cursor:
                    currentPage === 1 ? "not-allowed" : "pointer",
                }}
              >
                Previous
              </button>

              <button
                type="button"
                disabled={currentPage >= totalPages}
                onClick={handleNextPage}
                style={{
                  ...buttonStyle,
                  opacity: currentPage >= totalPages ? 0.5 : 1,
                  cursor:
                    currentPage >= totalPages
                      ? "not-allowed"
                      : "pointer",
                }}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
