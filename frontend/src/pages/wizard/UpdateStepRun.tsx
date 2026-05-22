import { useEffect, useRef, useState } from "react";
import { ActivityEvent } from "../../components/ActivityPanel";
import { UpdateIdentifyConfig } from "./UpdateStepIdentify";

// ── Types ──────────────────────────────────────────────────────────────────

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

interface UpdateRowResult {
  project_id: string;
  dataset_id: string;
  asset: string;
  asset_type: string;
  column_count: number;
  table_metadata: Record<string, unknown>;
  columns: CatalogColumn[];
  change_type: "new" | "modified";
}

interface UpdateDonePayload {
  rows_written: number;
  inserted: number;
  updated: number;
  registry_path: string;
  no_changes: boolean;
  rows: UpdateRowResult[];
}

type RunPhase = "running" | "done" | "error";

// ── Props ──────────────────────────────────────────────────────────────────

interface Props {
  config: UpdateIdentifyConfig;
  onAddEvent: (event: Omit<ActivityEvent, "id">) => void;
  onBack: () => void;
  onDone: () => void;
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

function ChangeBadge({ type }: { type: "new" | "modified" }) {
  if (type === "new") {
    return (
      <span className="inline-flex items-center gap-1 bg-green-50 text-green-700 border border-green-200 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
        New
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 border border-amber-200 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
      Modified
    </span>
  );
}

function ResultRow({ row }: { row: UpdateRowResult }) {
  const [expanded, setExpanded] = useState(false);
  const desc =
    typeof row.table_metadata?.description === "string"
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
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </td>
        <td className="px-4 py-2.5 text-xs">
          <ChangeBadge type={row.change_type} />
        </td>
        <td className="px-4 py-2.5 text-xs font-mono text-gray-700">{row.project_id}</td>
        <td className="px-4 py-2.5 text-xs text-gray-700">{row.dataset_id}</td>
        <td className="px-4 py-2.5 text-xs font-medium text-gray-900">{row.asset}</td>
        <td className="px-4 py-2.5 text-xs">
          <span className="inline-flex items-center gap-1 border border-gray-200 rounded px-1.5 py-0.5 text-gray-600">
            <svg
              className="w-3 h-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="3" y1="15" x2="21" y2="15" />
            </svg>
            {row.asset_type}
          </span>
        </td>
        <td className="px-4 py-2.5 text-xs text-gray-500">{row.column_count} columns</td>
        <td className="px-4 py-2.5 text-xs text-gray-500 max-w-[160px] truncate">
          {desc || "—"}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={8} className="px-6 py-4">
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

export default function UpdateStepRun({ config, onAddEvent, onBack, onDone }: Props) {
  const registryLabel = `${config.projectId}.${config.datasetId}.data_catalog_registry`;

  const [phase, setPhase] = useState<RunPhase>("running");
  const [status, setStatus] = useState("Starting update…");
  const [progressBars, setProgressBars] = useState<ProgressBar[]>([]);
  const [stats, setStats] = useState({ assets: 0, rowsWritten: 0 });
  const [elapsed, setElapsed] = useState(0);
  const [errorText, setErrorText] = useState("");
  const [result, setResult] = useState<UpdateDonePayload | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedRef = useRef(false);

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

    (async () => {
      try {
        const res = await fetch("/api/catalog/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_project_id: config.projectId,
            source_dataset_id: config.datasetId,
          }),
        });

        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

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
              upsertProgressBar(
                event.step as string,
                event.current as number,
                event.total as number,
              );
            } else if (event.type === "progress_write") {
              upsertProgressBar(
                event.step as string,
                event.current as number,
                event.total as number,
              );
              setStats((s) => ({ ...s, rowsWritten: event.current as number }));
            } else if (event.type === "stats") {
              setStats((s) => ({
                ...s,
                assets: (event.assets as number) ?? s.assets,
              }));
            } else if (event.type === "done") {
              const payload = event as unknown as UpdateDonePayload;
              setResult(payload);
              setStats((s) => ({ ...s, rowsWritten: payload.rows_written }));
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

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Running / Error ────────────────────────────────────────────────────

  if (phase === "running" || phase === "error") {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-xl">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            {phase === "running" ? (
              <svg
                className="w-5 h-5 text-blue-500 shrink-0 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-20"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="3"
                />
                <path
                  className="opacity-80"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8z"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5 text-red-500 shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            )}
            <div>
              <div className="text-sm font-semibold text-gray-900">
                {phase === "running" ? "Updating catalog in BigQuery" : "Update failed"}
              </div>
              <div className="text-xs text-blue-600 font-mono truncate max-w-xs">
                {registryLabel}
              </div>
            </div>
          </div>
          <button
            onClick={onBack}
            className="text-xs border border-gray-200 rounded px-3 py-1.5 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>

        {progressBars.length > 0 && (
          <div className="mb-4">
            {progressBars.map((bar) => (
              <ProgressRow key={bar.step} bar={bar} />
            ))}
          </div>
        )}

        <div className="flex gap-6 mb-5">
          <StatChip label="Elapsed" value={`${elapsed}s`} />
          <StatChip label="Rows written" value={stats.rowsWritten} />
          {stats.assets > 0 && <StatChip label="Assets discovered" value={stats.assets} />}
        </div>

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

  // ── Done: no changes ───────────────────────────────────────────────────

  if (result?.no_changes) {
    return (
      <div className="max-w-xl">
        <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600 shrink-0">
              <svg
                className="w-3.5 h-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            <div>
              <div className="text-sm font-semibold text-gray-900">
                Registry is up to date
              </div>
              <div className="text-xs text-blue-600 font-mono mt-0.5">
                {result.registry_path} — 0 total rows
              </div>
            </div>
          </div>
          <button
            onClick={onDone}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
            Done
          </button>
        </div>

        <div className="mt-3 border border-gray-100 rounded-lg bg-gray-50 px-4 py-3">
          <p className="text-xs text-gray-500">
            No new tables, columns, or metadata changes were detected. The registry
            already reflects the current state of{" "}
            <span className="font-mono text-blue-600">{config.datasetId}</span>.
          </p>
        </div>
      </div>
    );
  }

  // ── Done: with changes ─────────────────────────────────────────────────

  return (
    <div className="max-w-4xl">
      {/* Summary header */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-100 text-green-600 shrink-0">
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
          <div>
            <div className="text-sm font-semibold text-gray-900">
              Registry updated — incremental results
            </div>
            <div className="text-xs text-blue-600 font-mono mt-0.5">
              {result?.registry_path} —{" "}
              {result?.inserted ?? 0} inserted,{" "}
              {result?.updated ?? 0} updated
            </div>
          </div>
        </div>
        <button
          onClick={onDone}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          Done
        </button>
      </div>

      {/* Delta rows table */}
      {result && result.rows.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Incremental update results
            </span>
            <span className="text-xs text-gray-400">
              · {result.rows.length} row{result.rows.length !== 1 ? "s" : ""}
            </span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left border-b border-gray-100">
                <th className="px-4 py-2.5 w-6" />
                <th className="px-4 py-2.5 text-xs font-semibold text-gray-500">Change</th>
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
