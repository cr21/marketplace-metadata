export interface ActivityEvent {
  id: string;
  text: string;
  timestamp: string;
  type?: "tool" | "info" | "success" | "error";
  detail?: string;
}

interface ActivityPanelProps {
  events: ActivityEvent[];
  isLive?: boolean;
  elapsedSeconds?: number;
}

export default function ActivityPanel({ events, isLive = false, elapsedSeconds }: ActivityPanelProps) {
  return (
    <div className="w-72 shrink-0 border-l border-gray-200 bg-white flex flex-col h-screen sticky top-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="currentColor">
            <path d="M13 2L4.09 12.97 12 12.97 11 22 19.91 11.03 12 11.03z" />
          </svg>
          <span className="text-sm font-semibold text-gray-800">Activity</span>
          {isLive && (
            <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
              LIVE · {elapsedSeconds}s
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400">{events.length} events</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <p className="text-sm text-gray-400 px-4 pt-4">Agent actions will stream here...</p>
        ) : (
          <ul className="divide-y divide-gray-50">
            {events.map((event) => (
              <li key={event.id} className="px-4 py-2.5">
                <div className="flex items-start gap-2">
                  <EventIcon type={event.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-700 leading-snug">{event.text}</p>
                    {event.detail && (
                      <p className="text-[11px] text-gray-400 mt-0.5 font-mono truncate">{event.detail}</p>
                    )}
                    <p className="text-[10px] text-gray-300 mt-0.5">{event.timestamp}</p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function EventIcon({ type }: { type?: ActivityEvent["type"] }) {
  if (type === "tool") {
    return (
      <span className="mt-0.5 shrink-0 inline-flex items-center justify-center w-3.5 h-3.5 rounded bg-purple-100 text-purple-600">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
        </svg>
      </span>
    );
  }
  if (type === "success") {
    return (
      <span className="mt-0.5 shrink-0 inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-green-100 text-green-600">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </span>
    );
  }
  if (type === "error") {
    return (
      <span className="mt-0.5 shrink-0 inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-red-100 text-red-500">
        <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </span>
    );
  }
  return (
    <span className="mt-1.5 shrink-0 inline-block w-1.5 h-1.5 rounded-full bg-gray-300" />
  );
}
