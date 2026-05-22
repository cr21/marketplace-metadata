import { useState } from "react";
import { ActivityEvent } from "../../components/ActivityPanel";

interface StepProjectProps {
  initialProjectId?: string;
  onDatasetsListed: (projectId: string, selectedDataset: string) => void;
  onSubStepChange: (stepperStep: 1 | 2) => void;
  onAddEvent: (event: Omit<ActivityEvent, "id">) => void;
}

type SubStep = "enter-project" | "pick-dataset";

interface DatasetListResponse {
  project_id: string;
  datasets: string[];
}

export default function StepProject({
  initialProjectId = "",
  onDatasetsListed,
  onSubStepChange,
  onAddEvent,
}: StepProjectProps) {
  const [subStep, setSubStep] = useState<SubStep>("enter-project");
  const [projectId, setProjectId] = useState(initialProjectId);
  const [loading, setLoading] = useState(false);
  const [datasets, setDatasets] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");

  async function handleListDatasets() {
    if (!projectId.trim()) return;
    setLoading(true);
    setError("");

    onAddEvent({
      text: `Listing datasets in "${projectId.trim()}"`,
      timestamp: new Date().toLocaleTimeString(),
      type: "info",
    });

    try {
      const res = await fetch(`/api/datasets?project_id=${encodeURIComponent(projectId.trim())}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data: DatasetListResponse = await res.json();

      onAddEvent({
        text: `TOOL list_dataset_ids(projectId=${projectId.trim()})`,
        timestamp: new Date().toLocaleTimeString(),
        type: "tool",
      });
      onAddEvent({
        text: `Found ${data.datasets.length} dataset(s)`,
        timestamp: new Date().toLocaleTimeString(),
        type: "success",
      });

      setDatasets(data.datasets);
      setSelected("");
      setSubStep("pick-dataset");
      onSubStepChange(2);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      onAddEvent({
        text: `Failed to list datasets: ${msg}`,
        timestamp: new Date().toLocaleTimeString(),
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }

  function handleContinue() {
    if (!selected) return;
    onDatasetsListed(projectId.trim(), selected);
  }

  function handleBackToPicker() {
    setSubStep("enter-project");
    onSubStepChange(1);
  }

  if (subStep === "enter-project") {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-lg">
        <h2 className="text-base font-semibold text-gray-900 mb-1">Source project</h2>
        <p className="text-sm text-gray-500 mb-5">
          Which GCP project contains the dataset you want to catalog?
        </p>

        <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1.5">
          Project ID
        </label>
        <input
          type="text"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && handleListDatasets()}
          placeholder="my-gcp-project-id"
          className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
        />

        {error && <p className="text-xs text-red-500 mb-3">{error}</p>}

        <button
          onClick={handleListDatasets}
          disabled={!projectId.trim() || loading}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          {loading ? (
            <>
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Listing datasets…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              List datasets
            </>
          )}
        </button>
      </div>
    );
  }

  // pick-dataset sub-step
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-lg">
      <h2 className="text-base font-semibold text-gray-900 mb-1">Which dataset to catalog?</h2>
      <p className="text-sm text-gray-500 mb-5">
        Pick the dataset under{" "}
        <span className="text-blue-600 font-mono text-xs">{projectId}</span>{" "}
        whose tables and views the agent should crawl.
      </p>

      <ul className="space-y-2 mb-5">
        {datasets.map((ds) => (
          <li key={ds}>
            <label className="flex items-center gap-3 border border-gray-200 rounded-md px-4 py-2.5 cursor-pointer hover:border-blue-300 transition-colors">
              <input
                type="radio"
                name="dataset"
                value={ds}
                checked={selected === ds}
                onChange={() => setSelected(ds)}
                className="accent-blue-600"
              />
              <svg className="w-4 h-4 text-gray-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <path d="M8 21h8M12 17v4" />
              </svg>
              <span className="text-sm text-gray-700 font-mono">{ds}</span>
            </label>
          </li>
        ))}
      </ul>

      <div className="flex items-center gap-3">
        <button
          onClick={handleContinue}
          disabled={!selected}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6" />
          </svg>
          Continue
        </button>
        <button
          onClick={handleBackToPicker}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </button>
      </div>
    </div>
  );
}
