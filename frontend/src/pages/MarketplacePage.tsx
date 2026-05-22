import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

type Phase = "init" | "loaded" | "error";

interface StepState {
  text: string;
  status: "pending" | "in_progress" | "done";
}

interface ColumnRecord {
  name: string;
  data_type: string;
  description: string;
  is_pii: boolean;
}

interface CatalogItem {
  project_id: string;
  dataset_id: string;
  asset: string;
  asset_type: string;
  table_metadata: {
    description?: string;
    labels?: Record<string, string>;
    row_count?: number;
    size_bytes?: number;
    created?: string;
    modified?: string;
  };
  columns: ColumnRecord[];
  lineage: { upstream: number; downstream: number };
}

interface MarketplaceData {
  project_id: string;
  registry_path: string;
  registry_dataset: string;
  object_count: number;
  dataset_count: number;
  domain_count: number;
  lineage_edge_count: number;
  registry_version: number;
  last_crawled: string | null;
  catalog: CatalogItem[];
}

interface LineageEdge {
  direction: "UPSTREAM" | "DOWNSTREAM";
  source_fqn: string | null;
  target_fqn: string | null;
  source_column: string | null;
  target_column: string | null;
  confidence: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatSize(bytes?: number | null): string {
  if (!bytes) return "—";
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} KB`;
  return `${bytes} B`;
}

function parseFqn(fqn: string | null): string {
  if (!fqn) return "Unknown";
  // format: "bigquery:project.dataset.table" or "project.dataset.table"
  const parts = fqn.replace(/^bigquery:/, "").split(".");
  return parts[parts.length - 1];
}

function getDomainTag(item: CatalogItem): string {
  const labels = item.table_metadata.labels || {};
  const domain = labels.domain?.toUpperCase() ?? "";
  const category = labels.category?.toUpperCase() ?? "";
  if (domain && category) return `${domain} / ${category}`;
  return domain;
}

// ── Init Screen ────────────────────────────────────────────────────────────

function StepIcon({ status }: { status: StepState["status"] }) {
  if (status === "done") {
    return (
      <span className="shrink-0 w-5 h-5 rounded-full border-2 border-blue-500 flex items-center justify-center">
        <svg className="w-3 h-3 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <span className="shrink-0 w-5 h-5 rounded-full border-2 border-blue-400 flex items-center justify-center">
        <svg className="w-3 h-3 text-blue-400 animate-spin origin-center" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  return <span className="shrink-0 w-5 h-5 rounded-full border-2 border-gray-200" />;
}

function InitScreen({ steps }: { steps: StepState[] }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 w-[480px]">
        <div className="flex items-center gap-3 mb-7">
          <svg className="w-5 h-5 text-blue-500 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
          </svg>
          <h2 className="text-base font-semibold text-gray-900">Initialising Data Marketplace Agent...</h2>
        </div>
        <div className="space-y-4">
          {steps.map((step, i) => (
            <div key={i} className={`flex items-center gap-3 transition-opacity ${step.status === "pending" ? "opacity-35" : "opacity-100"}`}>
              <StepIcon status={step.status} />
              <span className="text-sm text-gray-700">{step.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Catalog Card ───────────────────────────────────────────────────────────

function CatalogCard({ item, onClick }: { item: CatalogItem; onClick: () => void }) {
  const description = item.table_metadata.description || "No description available.";
  const piiCount = item.columns.filter((c) => c.is_pii).length;
  const domainTag = getDomainTag(item);

  return (
    <button
      onClick={onClick}
      className="text-left bg-white border border-gray-200 rounded-xl p-4 hover:border-blue-300 hover:shadow-md transition-all group"
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded uppercase tracking-wider">
          {item.dataset_id}
        </span>
        <span className="text-[10px] font-medium text-gray-400 border border-gray-200 px-2 py-0.5 rounded uppercase">
          {item.asset_type}
        </span>
      </div>
      <h3 className="text-sm font-semibold text-gray-900 mb-1.5 group-hover:text-blue-700 transition-colors">
        {item.asset}
      </h3>
      <p className="text-xs text-gray-500 leading-relaxed mb-3 line-clamp-2">{description}</p>
      {domainTag && (
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2.5">{domainTag}</p>
      )}
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="3" y1="15" x2="21" y2="15" />
            <line x1="9" y1="3" x2="9" y2="21" />
          </svg>
          {item.columns.length}
        </span>
        {item.lineage.upstream > 0 && <span className="text-emerald-500">+{item.lineage.upstream}</span>}
        {item.lineage.downstream > 0 && <span className="text-blue-400">→{item.lineage.downstream}</span>}
        {piiCount > 0 && <span className="text-orange-400 ml-auto">⚠ {piiCount} PII</span>}
      </div>
    </button>
  );
}

// ── Columns Tab ────────────────────────────────────────────────────────────

function ColumnsTab({
  columns,
  lineageEdges,
}: {
  columns: ColumnRecord[];
  lineageEdges: LineageEdge[];
}) {
  const [expandedCol, setExpandedCol] = useState<string | null>(null);

  function getColLineage(colName: string) {
    // UPSTREAM edge: this asset receives data → target_column is the column in this asset
    const upstream = lineageEdges.filter(
      (e) => e.direction === "UPSTREAM" && e.target_column === colName && e.source_column
    );
    // DOWNSTREAM edge: this asset sends data → source_column is the column in this asset
    const downstream = lineageEdges.filter(
      (e) => e.direction === "DOWNSTREAM" && e.source_column === colName && e.target_column
    );
    return { upstream, downstream };
  }

  return (
    <div>
      <p className="text-xs text-gray-400 uppercase tracking-wider mb-4">
        {columns.length} columns — click to inspect
      </p>
      <div className="space-y-1">
        {columns.map((col) => {
          const isExpanded = expandedCol === col.name;
          const { upstream, downstream } = getColLineage(col.name);
          const hasColLineage = upstream.length > 0 || downstream.length > 0;

          return (
            <div key={col.name}>
              <button
                onClick={() => setExpandedCol(isExpanded ? null : col.name)}
                className={`w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors ${
                  isExpanded ? "bg-blue-50 border border-blue-100" : "hover:bg-gray-50"
                }`}
              >
                <span className="text-gray-300 font-mono text-sm mt-0.5 shrink-0">#</span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">{col.name}</span>
                    <span className="text-xs text-gray-400 font-mono">{col.data_type}</span>
                    {col.is_pii && (
                      <span className="text-[10px] bg-orange-50 text-orange-500 border border-orange-200 px-1.5 py-0.5 rounded font-medium">
                        PII
                      </span>
                    )}
                    {hasColLineage && (
                      <span className="text-[10px] bg-purple-50 text-purple-500 border border-purple-100 px-1.5 py-0.5 rounded font-medium">
                        lineage
                      </span>
                    )}
                  </div>
                  {col.description && (
                    <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{col.description}</p>
                  )}
                </div>
                <svg
                  className={`w-3.5 h-3.5 text-gray-400 shrink-0 mt-1 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                  viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {isExpanded && (
                <div className="ml-9 mr-3 mb-2 p-3 bg-gray-50 rounded-lg border border-gray-100 text-xs">
                  {!hasColLineage ? (
                    <p className="text-gray-400 italic">No column-level lineage recorded for this column.</p>
                  ) : (
                    <div className="space-y-3">
                      {upstream.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                            ← Upstream (feeds into this column)
                          </p>
                          <ul className="space-y-1">
                            {upstream.map((e, i) => (
                              <li key={i} className="flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                                <span className="font-mono text-gray-700">
                                  {parseFqn(e.source_fqn)}
                                  <span className="text-gray-400">.{e.source_column}</span>
                                </span>
                                <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded ${e.confidence === "HIGH" ? "bg-green-50 text-green-600" : "bg-yellow-50 text-yellow-600"}`}>
                                  {e.confidence}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {downstream.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                            → Downstream (this column feeds into)
                          </p>
                          <ul className="space-y-1">
                            {downstream.map((e, i) => (
                              <li key={i} className="flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
                                <span className="font-mono text-gray-700">
                                  {parseFqn(e.target_fqn)}
                                  <span className="text-gray-400">.{e.target_column}</span>
                                </span>
                                <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded ${e.confidence === "HIGH" ? "bg-green-50 text-green-600" : "bg-yellow-50 text-yellow-600"}`}>
                                  {e.confidence}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Lineage Tab ────────────────────────────────────────────────────────────

function LineageNode({
  label,
  sublabel,
  variant,
}: {
  label: string;
  sublabel?: string;
  variant: "upstream" | "current" | "downstream";
}) {
  const styles = {
    upstream: "bg-gray-50 border border-gray-200 text-gray-700",
    current: "bg-blue-500 border border-blue-500 text-white",
    downstream: "bg-gray-50 border border-gray-200 text-gray-700",
  };
  return (
    <div className={`rounded-lg px-4 py-2.5 text-center min-w-[130px] ${styles[variant]}`}>
      <p className="text-xs font-semibold leading-snug">{label}</p>
      {sublabel && (
        <p className={`text-[10px] mt-0.5 ${variant === "current" ? "text-blue-200" : "text-gray-400"}`}>
          {sublabel}
        </p>
      )}
    </div>
  );
}

function LineageTab({
  item,
  edges,
  loading,
}: {
  item: CatalogItem;
  edges: LineageEdge[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400">
        <svg className="w-5 h-5 animate-spin mr-2 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
        </svg>
        <span className="text-sm">Loading lineage...</span>
      </div>
    );
  }

  // Table-level edges only (no column pair) for the graph view
  const tableLevelEdges = edges.filter((e) => !e.source_column && !e.target_column);

  const upstreamFqns = [
    ...new Map(
      tableLevelEdges
        .filter((e) => e.direction === "UPSTREAM" && e.source_fqn)
        .map((e) => [e.source_fqn, e])
    ).values(),
  ];
  const downstreamFqns = [
    ...new Map(
      tableLevelEdges
        .filter((e) => e.direction === "DOWNSTREAM" && e.target_fqn)
        .map((e) => [e.target_fqn, e])
    ).values(),
  ];

  const hasTableLineage = upstreamFqns.length > 0 || downstreamFqns.length > 0;
  const colLineageCount = edges.filter((e) => e.source_column || e.target_column).length;

  if (!hasTableLineage && colLineageCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <svg className="w-12 h-12 mb-3 opacity-25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="6" r="3" />
          <circle cx="18" cy="18" r="3" />
          <line x1="9" y1="11" x2="15" y2="7" />
          <line x1="9" y1="13" x2="15" y2="17" />
        </svg>
        <p className="text-sm font-medium mb-1">No lineage data available</p>
        <p className="text-xs">Run the lineage fetcher to populate this view</p>
      </div>
    );
  }

  return (
    <div>
      {hasTableLineage && (
        <div className="flex items-start justify-center gap-6 py-6">
          {/* Upstream column */}
          {upstreamFqns.length > 0 && (
            <div className="flex flex-col items-center gap-2 pt-8">
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Upstream</p>
              {upstreamFqns.map((e, i) => (
                <LineageNode
                  key={i}
                  label={parseFqn(e.source_fqn)}
                  sublabel={e.confidence}
                  variant="upstream"
                />
              ))}
            </div>
          )}

          {/* Arrow */}
          {upstreamFqns.length > 0 && (
            <div className="flex items-center self-center mt-8">
              <div className="w-8 border-t-2 border-gray-300" />
              <svg className="w-3 h-3 text-gray-300 -ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="0,0 24,12 0,24" />
              </svg>
            </div>
          )}

          {/* Current table */}
          <div className="flex flex-col items-center self-center mt-8">
            <LineageNode
              label={item.asset}
              sublabel={item.dataset_id}
              variant="current"
            />
          </div>

          {/* Arrow */}
          {downstreamFqns.length > 0 && (
            <div className="flex items-center self-center mt-8">
              <div className="w-8 border-t-2 border-gray-300" />
              <svg className="w-3 h-3 text-gray-300 -ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="0,0 24,12 0,24" />
              </svg>
            </div>
          )}

          {/* Downstream column */}
          {downstreamFqns.length > 0 && (
            <div className="flex flex-col items-center gap-2 pt-8">
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Downstream</p>
              {downstreamFqns.map((e, i) => (
                <LineageNode
                  key={i}
                  label={parseFqn(e.target_fqn)}
                  sublabel={e.confidence}
                  variant="downstream"
                />
              ))}
            </div>
          )}
        </div>
      )}

      {colLineageCount > 0 && (
        <p className="text-center text-xs text-gray-400 mt-2">
          + {colLineageCount} column-level edges — click columns in the Columns tab to inspect
        </p>
      )}

      <p className="text-center text-[10px] text-gray-300 mt-4">
        — HIGH confidence &nbsp; - - - MEDIUM &nbsp; Click upstream/downstream nodes to navigate
      </p>
    </div>
  );
}

// ── SQL Tab ────────────────────────────────────────────────────────────────

function SqlTab({ item }: { item: CatalogItem }) {
  const topCols = item.columns.slice(0, 6);
  const remaining = item.columns.length - topCols.length;
  const colLines = topCols.map((c) => `  ${c.name}`).join(",\n");
  const sql = `SELECT\n${colLines}${remaining > 0 ? `,\n  -- ... and ${remaining} more columns` : ""}\nFROM \`${item.project_id}.${item.dataset_id}.${item.asset}\`\nLIMIT 100;`;

  return (
    <div>
      <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Sample Query</p>
      <pre className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-xs font-mono text-gray-800 overflow-x-auto whitespace-pre">
        {sql}
      </pre>
    </div>
  );
}

// ── Card Detail Modal ──────────────────────────────────────────────────────

type DetailTab = "columns" | "lineage" | "sql";

function CardDetailModal({
  item,
  registryDataset,
  onClose,
}: {
  item: CatalogItem;
  registryDataset: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<DetailTab>("columns");
  const [liveStats, setLiveStats] = useState<{ row_count: number | null; size_bytes: number | null } | null>(null);
  const [lineageEdges, setLineageEdges] = useState<LineageEdge[]>([]);
  const [lineageLoading, setLineageLoading] = useState(true);

  useEffect(() => {
    // Fetch live row count + size from BQ Table API
    fetch(
      `/api/marketplace/table-info?project_id=${encodeURIComponent(item.project_id)}&dataset_id=${encodeURIComponent(item.dataset_id)}&asset=${encodeURIComponent(item.asset)}`
    )
      .then((r) => r.json())
      .then((d) => setLiveStats(d))
      .catch(() => setLiveStats(null));

    // Fetch lineage edges
    setLineageLoading(true);
    fetch(
      `/api/marketplace/lineage?project_id=${encodeURIComponent(item.project_id)}&registry_dataset=${encodeURIComponent(registryDataset)}&asset=${encodeURIComponent(item.asset)}`
    )
      .then((r) => r.json())
      .then((d) => {
        setLineageEdges(d.edges ?? []);
        setLineageLoading(false);
      })
      .catch(() => {
        setLineageEdges([]);
        setLineageLoading(false);
      });
  }, [item.project_id, item.dataset_id, item.asset, registryDataset]);

  const meta = item.table_metadata;
  const labels = meta.labels || {};
  const rowCount = liveStats?.row_count ?? meta.row_count;
  const sizeBytes = liveStats?.size_bytes ?? meta.size_bytes;

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="flex-1" />
      <div
        className="w-[540px] bg-white shadow-2xl flex flex-col overflow-hidden border-l border-gray-100"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-gray-100 shrink-0">
          <div className="flex items-start justify-between gap-4 mb-3">
            <p className="text-xs text-gray-400 leading-relaxed">
              {item.project_id} › {item.dataset_id} › BASE TABLE
            </p>
            <button onClick={onClose} className="shrink-0 text-gray-400 hover:text-gray-600 transition-colors">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">{item.asset}</h2>
          <p className="text-sm text-gray-500 leading-relaxed">
            {meta.description || "No description available."}
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 border-b border-gray-100 divide-x divide-gray-100 shrink-0">
          {([
            ["COLUMNS", item.columns.length],
            ["ROWS", rowCount != null ? Number(rowCount).toLocaleString() : "—"],
            ["SIZE", formatSize(sizeBytes)],
            ["VERSION", "v1"],
          ] as [string, string | number][]).map(([label, value]) => (
            <div key={label} className="p-4 text-center">
              <div className="text-xl font-bold text-gray-900">{value}</div>
              <div className="text-[10px] text-gray-400 uppercase tracking-wider mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Labels row */}
        <div className="flex flex-wrap items-center gap-4 px-6 py-3 border-b border-gray-100 shrink-0">
          {(labels.domain || labels.category) && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <svg className="w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                <line x1="7" y1="7" x2="7.01" y2="7" />
              </svg>
              {[labels.domain, labels.category].filter(Boolean).join(" / ")}
            </span>
          )}
          {labels.owner && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <svg className="w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              {labels.owner}
            </span>
          )}
          {meta.modified && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <svg className="w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              Crawled {new Date(meta.modified).toLocaleDateString()}
            </span>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 px-6 shrink-0">
          {(["columns", "lineage", "sql"] as DetailTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? "border-blue-500 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t === "sql" ? "SQL Reference" : t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === "columns" && (
            <ColumnsTab columns={item.columns} lineageEdges={lineageEdges} />
          )}
          {tab === "lineage" && (
            <LineageTab item={item} edges={lineageEdges} loading={lineageLoading} />
          )}
          {tab === "sql" && <SqlTab item={item} />}
        </div>
      </div>
    </div>
  );
}

// ── Fetch Lineage Overlay ──────────────────────────────────────────────────

interface FetchLineageLogEntry {
  text: string;
  status: "in_progress" | "done" | "error";
  edgeCount?: number;
}

function FetchLineageOverlay({
  projectId,
  registryDataset,
  onDone,
  onClose,
}: {
  projectId: string;
  registryDataset: string;
  onDone: (totalEdges: number) => void;
  onClose: () => void;
}) {
  const [log, setLog] = useState<FetchLineageLogEntry[]>([]);
  const [totalEdges, setTotalEdges] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const appendLog = (entry: FetchLineageLogEntry) =>
      setLog((prev) => [...prev, entry]);

    const updateLast = (update: Partial<FetchLineageLogEntry>) =>
      setLog((prev) => {
        const next = [...prev];
        if (next.length > 0) next[next.length - 1] = { ...next[next.length - 1], ...update };
        return next;
      });

    fetch("/api/marketplace/fetch-lineage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, registry_dataset: registryDataset }),
      signal: ctrl.signal,
    })
      .then(async (res) => {
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const ev = JSON.parse(part.slice(6));

              if (ev.type === "setup") {
                if (ev.status === "in_progress") {
                  appendLog({ text: ev.text, status: "in_progress" });
                } else {
                  updateLast({ text: ev.text, status: "done" });
                }
              } else if (ev.type === "dataset_start") {
                appendLog({ text: ev.text, status: "in_progress" });
              } else if (ev.type === "dataset_done") {
                updateLast({ text: ev.text, status: "done", edgeCount: ev.edge_count });
              } else if (ev.type === "dataset_error") {
                updateLast({ text: ev.text, status: "error" });
              } else if (ev.type === "error") {
                setError(ev.text as string);
              } else if (ev.type === "done") {
                setTotalEdges(ev.total_edges as number);
                setDone(true);
                onDone(ev.total_edges as number);
              }
            } catch {
              // malformed chunk — ignore
            }
          }
        }
      })
      .catch((err: unknown) => {
        if ((err as Error).name !== "AbortError") setError(String(err));
      });

    return () => ctrl.abort();
  }, [projectId, registryDataset, onDone]);

  function LogIcon({ status }: { status: FetchLineageLogEntry["status"] }) {
    if (status === "done")
      return (
        <span className="shrink-0 w-4 h-4 rounded-full bg-green-100 flex items-center justify-center mt-0.5">
          <svg className="w-2.5 h-2.5 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
        </span>
      );
    if (status === "error")
      return (
        <span className="shrink-0 w-4 h-4 rounded-full bg-red-100 flex items-center justify-center mt-0.5">
          <svg className="w-2.5 h-2.5 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        </span>
      );
    return (
      <span className="shrink-0 w-4 h-4 rounded-full border-2 border-indigo-400 flex items-center justify-center mt-0.5">
        <svg className="w-2.5 h-2.5 text-indigo-400 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" /></svg>
      </span>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 w-[520px] max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 pt-6 pb-4 border-b border-gray-100 shrink-0">
          {!done && !error ? (
            <svg className="w-5 h-5 text-indigo-500 animate-spin shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
            </svg>
          ) : error ? (
            <span className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center shrink-0">
              <svg className="w-3 h-3 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </span>
          ) : (
            <span className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0">
              <svg className="w-3 h-3 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
            </span>
          )}
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              {done ? "Lineage Fetch Complete" : error ? "Lineage Fetch Failed" : "Fetching Lineage Data…"}
            </h2>
            {done && totalEdges !== null && (
              <p className="text-xs text-gray-500 mt-0.5">{totalEdges} edge(s) written to lineage_registry</p>
            )}
          </div>
        </div>

        {/* Log */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2.5">
          {log.map((entry, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <LogIcon status={entry.status} />
              <div className="flex-1 min-w-0">
                <span className="text-xs text-gray-700 leading-snug">{entry.text}</span>
                {entry.edgeCount !== undefined && entry.edgeCount > 0 && (
                  <span className="ml-2 text-[10px] font-semibold text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">
                    {entry.edgeCount} edges
                  </span>
                )}
              </div>
            </div>
          ))}
          {error && (
            <div className="p-3 bg-red-50 rounded-lg border border-red-100 text-xs text-red-600">{error}</div>
          )}
        </div>

        {/* Footer */}
        {(done || error) && (
          <div className="px-6 py-4 border-t border-gray-100 shrink-0">
            <button
              onClick={onClose}
              className="w-full py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Marketplace Main View ──────────────────────────────────────────────────

function MarketplaceMainView({
  data,
  onBack,
  onRecrawl,
}: {
  data: MarketplaceData;
  onBack: () => void;
  onRecrawl: () => void;
}) {
  const [search, setSearch] = useState("");
  const [datasetFilter, setDatasetFilter] = useState("ALL");
  const [domainFilter, setDomainFilter] = useState("ALL");
  const [selectedItem, setSelectedItem] = useState<CatalogItem | null>(null);
  const [showFetchLineage, setShowFetchLineage] = useState(false);
  const [lineageEdgeCount, setLineageEdgeCount] = useState(data.lineage_edge_count);
  const [lineageRefreshKey, setLineageRefreshKey] = useState(0);

  function handleLineageFetchDone(newEdges: number) {
    setLineageEdgeCount((prev) => prev + newEdges);
    setLineageRefreshKey((k) => k + 1);
  }

  const datasets = ["ALL", ...Array.from(new Set(data.catalog.map((i) => i.dataset_id))).sort()];
  const domains = [
    "ALL",
    ...Array.from(
      new Set(
        data.catalog
          .map((i) => i.table_metadata.labels?.domain)
          .filter((d): d is string => Boolean(d))
      )
    ).sort(),
  ];

  const filtered = data.catalog.filter((item) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      item.asset.toLowerCase().includes(q) ||
      (item.table_metadata.description ?? "").toLowerCase().includes(q) ||
      item.dataset_id.toLowerCase().includes(q);
    const matchesDataset = datasetFilter === "ALL" || item.dataset_id === datasetFilter;
    const matchesDomain =
      domainFilter === "ALL" || item.table_metadata.labels?.domain === domainFilter;
    return matchesSearch && matchesDataset && matchesDomain;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-500 rounded-lg flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-none">Data Marketplace Agent</h1>
            <p className="text-xs text-gray-400 mt-0.5">{data.project_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            Ask Insight Store
          </button>
          <button
            onClick={() => setShowFetchLineage(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="6" r="3" />
              <circle cx="18" cy="18" r="3" />
              <line x1="9" y1="11" x2="15" y2="7" />
              <line x1="9" y1="13" x2="15" y2="17" />
            </svg>
            Fetch Lineage
          </button>
          <button
            onClick={onRecrawl}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Recrawl
          </button>
          <button
            onClick={onBack}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {/* Registry banner */}
      <div className="mx-6 mt-5 bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <svg className="w-3 h-3 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
          <span className="text-sm font-semibold text-gray-800">Found Data Catalog Registry</span>
          <span className="text-[10px] font-bold text-blue-500 bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded">
            v{data.registry_version}
          </span>
        </div>
        <p className="text-xs text-gray-400 mb-5 ml-7">
          {data.registry_path}
          {data.last_crawled
            ? ` · last crawled ${new Date(data.last_crawled).toLocaleString("en-US", { timeZoneName: "short" })}`
            : ""}
        </p>
        <div className="grid grid-cols-4 gap-6">
          {([
            [data.object_count, "Objects Catalogued"],
            [data.dataset_count, "Datasets"],
            [data.domain_count, "Business Domains"],
            [lineageEdgeCount, "Lineage Edges"],
          ] as [number, string][]).map(([value, label]) => (
            <div key={label}>
              <div className="text-3xl font-bold text-gray-900">{value}</div>
              <div className="text-[10px] text-gray-400 uppercase tracking-wider mt-1">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Search + filters */}
      <div className="mx-6 mt-4 flex items-center gap-3">
        <div className="relative w-72">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search objects, descriptions, columns..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-300 bg-white"
          />
        </div>
        <select
          value={datasetFilter}
          onChange={(e) => setDatasetFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200 bg-white text-gray-700"
        >
          {datasets.map((d) => (
            <option key={d} value={d}>Dataset: {d}</option>
          ))}
        </select>
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200 bg-white text-gray-700"
        >
          {domains.map((d) => (
            <option key={d} value={d}>Domain: {d}</option>
          ))}
        </select>
        <span className="ml-auto text-xs text-gray-400">
          {filtered.length} of {data.object_count} objects
        </span>
      </div>

      {/* Catalog grid */}
      <div className="mx-6 mt-4 mb-10 grid grid-cols-3 gap-4">
        {filtered.map((item) => (
          <CatalogCard
            key={`${item.dataset_id}.${item.asset}`}
            item={item}
            onClick={() => setSelectedItem(item)}
          />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-3 flex flex-col items-center justify-center py-20 text-gray-400">
            <svg className="w-10 h-10 mb-3 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <p className="text-sm">No objects match your search</p>
          </div>
        )}
      </div>

      {selectedItem && (
        <CardDetailModal
          key={`${selectedItem.dataset_id}.${selectedItem.asset}-${lineageRefreshKey}`}
          item={selectedItem}
          registryDataset={data.registry_dataset}
          onClose={() => setSelectedItem(null)}
        />
      )}

      {showFetchLineage && (
        <FetchLineageOverlay
          projectId={data.project_id}
          registryDataset={data.registry_dataset}
          onDone={handleLineageFetchDone}
          onClose={() => setShowFetchLineage(false)}
        />
      )}
    </div>
  );
}

// ── Main Export ────────────────────────────────────────────────────────────

interface MarketplacePageProps {
  projectId: string;
  onBack: () => void;
}

export default function MarketplacePage({ projectId, onBack }: MarketplacePageProps) {
  const [phase, setPhase] = useState<Phase>("init");
  const [steps, setSteps] = useState<StepState[]>([
    { text: `Connecting to BigQuery project ${projectId}`, status: "pending" },
    { text: "Scanning INFORMATION_SCHEMA across datasets", status: "pending" },
    { text: "Finding data_catalog_registry", status: "pending" },
    { text: "Loading persisted objects", status: "pending" },
  ]);
  const [data, setData] = useState<MarketplaceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const runInit = useCallback(() => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setPhase("init");
    setData(null);
    setError(null);
    setSteps([
      { text: `Connecting to BigQuery project ${projectId}`, status: "pending" },
      { text: "Scanning INFORMATION_SCHEMA across datasets", status: "pending" },
      { text: "Finding data_catalog_registry", status: "pending" },
      { text: "Loading persisted objects", status: "pending" },
    ]);

    fetch("/api/marketplace/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId }),
      signal: ctrl.signal,
    })
      .then(async (res) => {
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(part.slice(6));
              if (event.type === "step") {
                setSteps((prev) => {
                  const next = [...prev];
                  const idx = (event.step as number) - 1;
                  if (idx >= 0 && idx < next.length) {
                    next[idx] = { text: event.text ?? next[idx].text, status: event.status };
                  }
                  return next;
                });
              } else if (event.type === "error") {
                setError(event.text as string);
                setPhase("error");
              } else if (event.type === "done") {
                setData(event as unknown as MarketplaceData);
                setPhase("loaded");
              }
            } catch {
              // malformed SSE chunk — ignore
            }
          }
        }
      })
      .catch((err: unknown) => {
        if ((err as Error).name !== "AbortError") {
          setError(String(err));
          setPhase("error");
        }
      });
  }, [projectId]);

  useEffect(() => {
    runInit();
    return () => abortRef.current?.abort();
  }, [runInit]);

  if (phase === "init") return <InitScreen steps={steps} />;

  if (phase === "error") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 max-w-md text-center">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-base font-semibold text-gray-900 mb-2">Initialization Failed</h2>
          <p className="text-sm text-gray-500 mb-6 leading-relaxed">{error}</p>
          <div className="flex gap-3 justify-center">
            <button onClick={onBack} className="px-5 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              Back
            </button>
            <button onClick={runInit} className="px-5 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors">
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <MarketplaceMainView data={data!} onBack={onBack} onRecrawl={runInit} />;
}
