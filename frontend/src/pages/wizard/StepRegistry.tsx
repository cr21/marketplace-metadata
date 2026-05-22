import { useState } from "react";

export interface RegistryConfig {
  project: string;
  dataset: string;
  table: string;
}

interface StepRegistryProps {
  projectId: string;
  selectedDataset: string; // "project:dataset" format
  onConfirm: (registry: RegistryConfig) => void;
  onBack: () => void;
}

function datasetName(d: string) {
  // "project:dataset" → "dataset", or passthrough if no colon
  return d.includes(":") ? d.split(":")[1] : d;
}

export default function StepRegistry({ projectId, selectedDataset, onConfirm, onBack }: StepRegistryProps) {
  const [expanded, setExpanded] = useState(false);
  const [regProject, setRegProject] = useState(projectId); // used in expanded form + onConfirm
  const [regDataset, setRegDataset] = useState(selectedDataset);
  const [regTable, setRegTable] = useState("data_catalog_registry");

  // regDataset is already "project:dataset" — fullPath is "project:dataset.table"
  const fullPath = `${regDataset}.${regTable}`;

  function handleConfirm() {
    onConfirm({ project: regProject, dataset: datasetName(regDataset), table: regTable });
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-lg">
      <h2 className="text-base font-semibold text-gray-900 mb-1">Where should the registry live?</h2>
      <p className="text-sm text-gray-500 mb-5">
        The agent will crawl{" "}
        <span className="text-blue-600 font-mono text-xs">{selectedDataset}</span>{" "}
        and write the catalog rows to a real BigQuery table. Pick where it should land.
      </p>

      {/* Info box */}
      <div className="border border-gray-200 rounded-md p-3 mb-5 bg-gray-50">
        <p className="text-xs text-gray-500 mb-1">
          Registry table will be created at{" "}
          <span className="text-blue-600 font-mono font-medium">{fullPath}</span>{" "}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-blue-500 hover:text-blue-700 underline ml-1"
          >
            {expanded ? "Hide" : "Change destination"}
          </button>
        </p>

        {expanded && (
          <div className="mt-4 space-y-3">
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Registry Project
              </label>
              <input
                type="text"
                value={regProject}
                onChange={(e) => setRegProject(e.target.value)}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Registry Dataset{" "}
                <span className="normal-case font-normal">(must already exist)</span>
              </label>
              <input
                type="text"
                value={regDataset}
                onChange={(e) => setRegDataset(e.target.value)}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Registry Table Name
              </label>
              <input
                type="text"
                value={regTable}
                onChange={(e) => setRegTable(e.target.value)}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleConfirm}
          disabled={!regProject.trim() || !regDataset.trim() || !regTable.trim()}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5,3 19,12 5,21" />
          </svg>
          Build catalog in BigQuery
        </button>
        <button
          onClick={onBack}
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
