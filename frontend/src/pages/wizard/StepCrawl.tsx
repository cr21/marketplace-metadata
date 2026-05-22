import { useEffect, useRef, useState } from "react";
import { ActivityEvent } from "../../components/ActivityPanel";
import { RegistryConfig } from "./StepRegistry";

// ── Types ─────────────────────────────────────────────────────────────────

interface BuildRequest {
  source_project_id: string;
  source_dataset_id: string;
  registry_project: string;
  registry_dataset: string;
  registry_table: string;
}

interface ProgressBar {
  step: string;
  current: number;
  total: number;
}

interface CatalogColumn {
  name: string;
  data_type: string;
  description: string;
  is_pii: boolean;
}

interface CatalogRowResult {
  project_id: string;
  dataset_id: string;
  asset: string;
  asset_type: string;
  column_count: number;
  table_metadata: Record<string, unknown>;
  columns: CatalogColumn[];
}

interface DonePayload {
  rows_written: number;
  registry_path: string;
  rows: CatalogRowResult[];
}

type CrawlPhase = "running" | "done" | "error";

// ── Props ──────────────────────────────────────────────────────────────────

interface StepCrawlProps {
  sourceProjectId: string;
  selectedDataset: string; // "project:dataset"
  registry: RegistryConfig;
  onAddEvent: (event: Omit<ActivityEvent, "id">) => void;
  onBack: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function extractDatasetId(ds: string): string {
  return ds.includes(":") ? ds.split(":")[1] : ds;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ProgressRow({ bar }: { bar: ProgressBar }) {
  const percent = bar.total === 0 ? 0 : Math.round((bar.current / bar.total) * 100);
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
        <span>{bar.step}</span>
        <span className="text-gray-400">
          {bar.current}/{bar.total} · {percent}%
        </span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-lg font-bold text-gray-900">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
    </div>
  );
}

function ResultRow({ row }: { row: CatalogRowResult }) {
  const [expanded, setExpanded] = useState(false);
  const desc = typeof row.table_metadata?.description === "string"
    ? row.table_metadata.description
    : "";

  return (
    <>
      <tr
        className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-2.5 text-xs text-gray-400">
          <svg
            className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </td>
        <td className="px-4 py-2.5 text-xs font-mono text-gray-700">{row.project_id}</td>
        <td className="px-4 py-2.5 text-xs text-gray-700">{row.dataset_id}</td>
        <td className="px-4 py-2.5 text-xs font-medium text-gray-900">{row.asset}</td>
        <td className="px-4 py-2.5 text-xs">
          <span className="inline-flex items-center gap-1 border border-gray-200 rounded px-1.5 py-0.5 text-gray-600">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="3" y1="15" x2="21" y2="15" />
            </svg>
            {row.asset_type}
          </span>
        </td>
        <td className="px-4 py-2.5 text-xs text-gray-500">{row.column_count} columns</td>
        <td className="px-4 py-2.5 text-xs text-gray-500 max-w-[180px] truncate">
          {desc || "—"}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={7} className="px-6 py-4">
            {desc && (
              <div className="mb-4">
                <div className="text-[10px] uppercase tracking-wide font-semibold text-gray-400 mb-1">
                  Table Metadata
                </div>
                <p className="text-xs text-gray-600">{desc}</p>
              </div>
            )}
            <div className="text-[10px] uppercase tracking-wide font-semibold text-gray-400 mb-2">
              Columns ({row.columns.length})
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-200">
                  <th className="pb-1 pr-4 font-medium">Name</th>
                  <th className="pb-1 pr-4 font-medium">Type</th>
                  <th className="pb-1 pr-4 font-medium">PII</th>
                  <th className="pb-1 font-medium">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {row.columns.map((col) => (
                  <tr key={col.name}>
                    <td className="py-1.5 pr-4 font-mono text-gray-800">{col.name}</td>
                    <td className="py-1.5 pr-4 text-gray-400 font-mono">{col.data_type}</td>
                    <td className="py-1.5 pr-4">
                      {col.is_pii ? (
                        <span className="inline-flex items-center gap-1 bg-red-50 text-red-600 border border-red-200 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500" />
                          PII
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-1.5 text-gray-500">{col.description || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function StepCrawl({
  sourceProjectId,
  selectedDataset,
  registry,
  onAddEvent,
  onBack,
}: StepCrawlProps) {
  const sourceDatasetId = extractDatasetId(selectedDataset);
  const sourceLabel = `${sourceDatasetId} → ${registry.project}.${registry.dataset}.${registry.table}`;

  const [phase, setPhase] = useState<CrawlPhase>("running");
  const [status, setStatus] = useState("Spinning up workers…");
  const [progressBars, setProgressBars] = useState<ProgressBar[]>([]);
  const [stats, setStats] = useState({ datasets: 0, assets: 0, rowsWritten: 0 });
  const [elapsed, setElapsed] = useState(0);
  const [errorText, setErrorText] = useState("");
  const [result, setResult] = useState<DonePayload | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedRef = useRef(false); // guard against React StrictMode double-invoke

  function upsertProgressBar(step: string, current: number, total: number) {
    setProgressBars((prev) => {
      const idx = prev.findIndex((b) => b.step === step);
      if (idx === -1) return [...prev, { step, current, total }];
      const next = [...prev];
      next[idx] = { step, current, total };
      return next;
    });
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);

    const req: BuildRequest = {
      source_project_id: sourceProjectId,
      source_dataset_id: sourceDatasetId,
      registry_project: registry.project,
      registry_dataset: registry.dataset,
      registry_table: registry.table,
    };

    (async () => {
      try {
        const res = await fetch("/api/catalog/build", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(req),
        });

        if (!res.ok || !res.body) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const event = JSON.parse(line.slice(6)) as Record<string, unknown>;

            if (event.type === "activity") {
              onAddEvent({
                text: event.text as string,
                timestamp: new Date().toLocaleTimeString(),
                type: (event.event_type as ActivityEvent["type"]) ?? "info",
              });
            } else if (event.type === "status") {
              setStatus(event.text as string);
            } else if (event.type === "progress") {
              upsertProgressBar(event.step as string, event.current as number, event.total as number);
            } else if (event.type === "progress_write") {
              upsertProgressBar(event.step as string, event.current as number, event.total as number);
              setStats((s) => ({ ...s, rowsWritten: event.current as number }));
            } else if (event.type === "stats") {
              setStats((s) => ({
                ...s,
                datasets: (event.datasets as number) ?? s.datasets,
                assets: (event.assets as number) ?? s.assets,
              }));
            } else if (event.type === "done") {
              setResult(event as unknown as DonePayload);
              setStats((s) => ({ ...s, rowsWritten: (event as unknown as DonePayload).rows_written }));
              setPhase("done");
              if (timerRef.current) clearInterval(timerRef.current);
            } else if (event.type === "error") {
              setErrorText(event.text as string);
              setPhase("error");
              if (timerRef.current) clearInterval(timerRef.current);
            }
          }
        }
      } catch (e) {
        setErrorText(e instanceof Error ? e.message : String(e));
        setPhase("error");
        if (timerRef.current) clearInterval(timerRef.current);
      }
    })();

    // Cleanup only clears the timer — the fetch runs to completion regardless.
    // startedRef guard above ensures StrictMode double-invoke never starts a second build.
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Running state ──────────────────────────────────────────────────────

  if (phase === "running" || phase === "error") {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <svg
              className="w-5 h-5 text-blue-500 shrink-0 animate-spin"
              viewBox="0 0 24 24" fill="none"
            >
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <div>
              <div className="text-sm font-semibold text-gray-900">Building catalog in BigQuery</div>
              <div className="text-xs text-blue-600 font-mono truncate max-w-xs">{sourceLabel}</div>
            </div>
          </div>
          <button
            onClick={onBack}
            className="text-xs border border-gray-200 rounded px-3 py-1.5 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>

        {/* Progress bars */}
        {progressBars.length > 0 && (
          <div className="mb-4">
            {progressBars.map((bar) => (
              <ProgressRow key={bar.step} bar={bar} />
            ))}
          </div>
        )}

        {/* Stats */}
        <div className="flex gap-6 mb-5">
          <StatChip label="Elapsed" value={`${elapsed}s`} />
          <StatChip label="Rows written" value={stats.rowsWritten} />
          {stats.datasets > 0 && <StatChip label="Datasets" value={stats.datasets} />}
          {stats.assets > 0 && <StatChip label="Assets discovered" value={stats.assets} />}
        </div>

        {/* Status area */}
        <div className="border border-gray-100 rounded-md bg-gray-50 px-4 py-3 min-h-[56px]">
          {phase === "error" ? (
            <p className="text-xs text-red-500">{errorText}</p>
          ) : (
            <>
              <p className="text-xs text-gray-500">{status}</p>
              <p className="text-xs text-gray-400 italic mt-1">
                Live tool calls in the Activity panel →
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  // ── Done state ─────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl">
      {/* Done header */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
          <div>
            <div className="text-sm font-semibold text-gray-900">Registry written to BigQuery</div>
            <div className="text-xs text-blue-600 font-mono">
              {result?.registry_path} — {result?.rows_written} row{result?.rows_written !== 1 ? "s" : ""}
            </div>
          </div>
        </div>
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          Done
        </button>
      </div>

      {/* Results table */}
      {result && result.rows.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-4 py-2.5 w-6" />
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Project</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Dataset</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Asset</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Type</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Columns</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Table Metadata</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row) => (
                <ResultRow key={`${row.dataset_id}.${row.asset}`} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
