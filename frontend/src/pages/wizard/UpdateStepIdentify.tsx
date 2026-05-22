import { useState } from "react";

export interface UpdateIdentifyConfig {
  projectId: string;
  datasetId: string;
}

interface Props {
  onSubmit: (config: UpdateIdentifyConfig) => void;
  onBack: () => void;
}

export default function UpdateStepIdentify({ onSubmit, onBack }: Props) {
  const [projectId, setProjectId] = useState("");
  const [datasetId, setDatasetId] = useState("");

  const canSubmit = projectId.trim() !== "" && datasetId.trim() !== "";

  function handleSubmit() {
    if (!canSubmit) return;
    onSubmit({ projectId: projectId.trim(), datasetId: datasetId.trim() });
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-lg">
      <h2 className="text-base font-semibold text-gray-900 mb-1">
        Identify your catalog
      </h2>
      <p className="text-sm text-gray-500 mb-5">
        Provide the GCP project and dataset that contains your existing catalog.
        The agent will read{" "}
        <span className="font-mono text-blue-600 text-xs">data_catalog_registry</span>
        , re-crawl{" "}
        <span className="font-mono text-blue-600 text-xs">INFORMATION_SCHEMA</span>
        , and write only the new or changed rows.
      </p>

      <div className="space-y-4 mb-5">
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1.5">
            Project ID
          </label>
          <input
            type="text"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canSubmit && handleSubmit()}
            placeholder="my-gcp-project-id"
            className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1.5">
            Dataset Name
          </label>
          <input
            type="text"
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canSubmit && handleSubmit()}
            placeholder="my_dataset"
            className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Registry note */}
      <div className="border border-gray-100 rounded-md bg-gray-50 px-3 py-2.5 mb-5">
        <p className="text-xs text-gray-500">
          Registry table assumed at{" "}
          <span className="font-mono text-blue-600">
            {projectId || "<project>"}.{datasetId || "<dataset>"}.data_catalog_registry
          </span>
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          Update registry
        </button>
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </button>
      </div>
    </div>
  );
}
