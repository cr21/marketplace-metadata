import { useState } from "react";

interface MarketplaceModalProps {
  onClose: () => void;
  onExplore: (projectId: string) => void;
}

export default function MarketplaceModal({ onClose, onExplore }: MarketplaceModalProps) {
  const [projectId, setProjectId] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (projectId.trim()) onExplore(projectId.trim());
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-[420px] p-6 border border-gray-100">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-gray-900">Explore Data Marketplace</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <p className="text-sm text-gray-500 mb-5 leading-relaxed">
          Enter your GCP Project ID to browse the data catalog registry and discover all catalogued assets.
        </p>

        <form onSubmit={handleSubmit}>
          <label className="block text-xs font-medium text-gray-600 mb-1.5">GCP Project ID</label>
          <input
            type="text"
            placeholder="e.g. my-gcp-project-123"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            autoFocus
            className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 placeholder:text-gray-300 mb-5"
          />

          <div className="flex gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!projectId.trim()}
              className="flex-1 py-2.5 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium"
            >
              Explore
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
