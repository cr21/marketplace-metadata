import { useCallback, useEffect, useRef, useState } from "react";
import ActivityPanel, { ActivityEvent } from "./components/ActivityPanel";
import MarketplaceModal from "./components/MarketplaceModal";
import LandingPage from "./pages/LandingPage";
import BuildWizard from "./pages/BuildWizard";
import UpdateWizard from "./pages/UpdateWizard";
import MarketplacePage from "./pages/MarketplacePage";

interface HealthData {
  status: string;
  gcp_project: string;
  bq_reachable: boolean;
  lineage_api_reachable: boolean;
}

type AppView = "landing" | "build" | "update" | "marketplace";

function useHealth() {
  const [data, setData] = useState<HealthData | null>(null);
  useEffect(() => {
    fetch("/health")
      .then((r) => r.json() as Promise<HealthData>)
      .then(setData)
      .catch(() => null);
  }, []);
  return data;
}

export default function App() {
  const health = useHealth();
  const [view, setView] = useState<AppView>("landing");
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [showMarketplaceModal, setShowMarketplaceModal] = useState(false);
  const [marketplaceProjectId, setMarketplaceProjectId] = useState("");
  const eventIdRef = useRef(0);

  const addEvent = useCallback((event: Omit<ActivityEvent, "id">) => {
    setEvents((prev) => [
      ...prev,
      { ...event, id: String(++eventIdRef.current) },
    ]);
  }, []);

  function handleNavigate(v: AppView) {
    if (v !== view) setEvents([]);
    setView(v);
  }

  function handleOpenMarketplace(projectId: string) {
    setMarketplaceProjectId(projectId);
    setShowMarketplaceModal(false);
    handleNavigate("marketplace");
  }

  const isMarketplace = view === "marketplace";

  return (
    <div className="flex min-h-screen bg-gray-50">
      <main className="flex-1 min-w-0 relative">
        {/* Go To Marketplace button — visible on landing, top-right of main area */}
        {view === "landing" && (
          <div className="absolute top-4 right-4 z-10">
            <button
              onClick={() => setShowMarketplaceModal(true)}
              className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-blue-600 bg-white border border-blue-200 rounded-lg hover:bg-blue-50 hover:border-blue-400 shadow-sm transition-all"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
              Go To Marketplace
            </button>
          </div>
        )}

        {view === "landing" && (
          <LandingPage
            bqReachable={health?.bq_reachable ?? false}
            gcpProject={health?.gcp_project ?? ""}
            onBuildNew={() => handleNavigate("build")}
            onUpdateExisting={() => handleNavigate("update")}
          />
        )}
        {view === "build" && (
          <BuildWizard
            onBack={() => handleNavigate("landing")}
            onAddEvent={addEvent}
          />
        )}
        {view === "update" && (
          <UpdateWizard
            onBack={() => handleNavigate("landing")}
            onAddEvent={addEvent}
          />
        )}
        {view === "marketplace" && (
          <MarketplacePage
            projectId={marketplaceProjectId}
            onBack={() => handleNavigate("landing")}
          />
        )}
      </main>

      {/* Activity panel is hidden in marketplace view (marketplace has its own full-width layout) */}
      {!isMarketplace && <ActivityPanel events={events} />}

      {showMarketplaceModal && (
        <MarketplaceModal
          onClose={() => setShowMarketplaceModal(false)}
          onExplore={handleOpenMarketplace}
        />
      )}
    </div>
  );
}
