import { useCallback, useEffect, useRef, useState } from "react";
import ActivityPanel, { ActivityEvent } from "./components/ActivityPanel";
import LandingPage from "./pages/LandingPage";
import BuildWizard from "./pages/BuildWizard";
import UpdateWizard from "./pages/UpdateWizard";

interface HealthData {
  status: string;
  gcp_project: string;
  bq_reachable: boolean;
  lineage_api_reachable: boolean;
}

type AppView = "landing" | "build" | "update";

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
  const eventIdRef = useRef(0);

  const addEvent = useCallback((event: Omit<ActivityEvent, "id">) => {
    setEvents((prev) => [
      ...prev,
      { ...event, id: String(++eventIdRef.current) },
    ]);
  }, []);

  function handleNavigate(v: AppView) {
    if (v !== view) setEvents([]); // clear panel when switching flows
    setView(v);
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <main className="flex-1 min-w-0">
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
      </main>
      <ActivityPanel events={events} />
    </div>
  );
}
