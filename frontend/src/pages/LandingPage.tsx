interface ActionCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}

function ActionCard({ icon, title, description, onClick }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      className="relative text-left border border-gray-200 rounded-lg p-5 bg-white hover:border-blue-300 hover:shadow-sm transition-all group"
    >
      <span className="absolute top-4 right-4 text-gray-300 group-hover:text-blue-400 transition-colors">
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </span>
      <span className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-200 text-gray-500 mb-3 group-hover:border-blue-200 group-hover:text-blue-500 transition-colors">
        {icon}
      </span>
      <h3 className="text-sm font-semibold text-gray-900 mb-1.5">{title}</h3>
      <p className="text-xs text-gray-500 leading-relaxed">{description}</p>
    </button>
  );
}

interface LandingPageProps {
  bqReachable: boolean;
  gcpProject: string;
  onBuildNew: () => void;
  onUpdateExisting: () => void;
}

export default function LandingPage({ bqReachable, gcpProject, onBuildNew, onUpdateExisting }: LandingPageProps) {
  return (
    <div className="p-10">
      <div className="inline-flex items-center gap-1.5 text-xs text-gray-500 mb-6">
        <svg className="w-3.5 h-3.5 text-blue-500" viewBox="0 0 24 24" fill="currentColor">
          <path d="M13 2L4.09 12.97 12 12.97 11 22 19.91 11.03 12 11.03z" />
        </svg>
        {bqReachable ? (
          <span>Connected to BigQuery via MCP</span>
        ) : (
          <span className="text-red-400">BigQuery unreachable</span>
        )}
        {gcpProject && <span className="text-gray-400">· {gcpProject}</span>}
      </div>

      <h1 className="text-3xl font-bold text-gray-900 mb-2">Data Catalog Agent</h1>
      <p className="text-gray-500 text-sm leading-relaxed max-w-lg mb-10">
        Crawl your BigQuery datasets, generate column-level metadata, and materialize a Data
        Catalog Registry as a real BigQuery table.
      </p>

      <div className="grid grid-cols-2 gap-4 max-w-xl">
        <ActionCard
          icon={
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          }
          title="Build a new catalog"
          description="Point at a GCP project. The agent crawls INFORMATION_SCHEMA across every dataset, generates metadata, then CREATE TABLEs the registry and INSERTs every row."
          onClick={onBuildNew}
        />
        <ActionCard
          icon={
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          }
          title="Update an existing catalog"
          description="Point at a source dataset and an existing registry table. The agent SELECTs the registry, re-crawls, and INSERTs only the new entries."
          onClick={onUpdateExisting}
        />
      </div>
    </div>
  );
}
