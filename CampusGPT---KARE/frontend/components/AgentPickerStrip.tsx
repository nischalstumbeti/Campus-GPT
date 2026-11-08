"use client";

import type { AgentType } from "@/hooks/useChat";
import { getAgentTheme, type AgentTheme } from "@/lib/agentThemes";
import { agentsForRole } from "@/lib/agentsByRole";
import { useAuth } from "@/hooks/useAuth";
import AgentAvatar from "./AgentAvatar";

const SHORT: Record<AgentType, string> = {
  general: "Guide",
  academic: "Academics",
  faculty: "Faculty",
  admission: "Admission",
  reception: "Reception",
  hostel: "Hostel",
  warden: "Warden",
};

export default function AgentPickerStrip({
  agent,
  onSelect,
  agents,
}: {
  agent: AgentType;
  onSelect: (id: AgentType) => void;
  agents?: AgentTheme[];
}) {
  const { user } = useAuth();
  const list =
    agents ||
    agentsForRole(user?.role, {
      residenceType: user?.residence_type,
      isHosteller: user?.is_hosteller,
    });
  const theme = getAgentTheme(agent);

  return (
    <div
      className="relative z-20 shrink-0 border-b backdrop-blur-md"
      style={{ borderColor: `${theme.primary}22`, backgroundColor: "rgba(255,255,255,0.88)" }}
    >
      <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 text-center">
        Choose an assistant · separate chat per role
      </p>
      <div className="overflow-x-auto scrollbar-thin">
        <div className="flex justify-start sm:justify-center gap-2 px-3 pb-3 min-w-max sm:min-w-0 mx-auto">
          {list.map((a) => {
            const active = agent === a.id;
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => onSelect(a.id)}
                className={`flex flex-col items-center justify-start w-[72px] sm:w-[80px] h-[88px] sm:h-[92px] px-1.5 pt-2 pb-1.5 rounded-2xl border transition-all shrink-0 ${
                  active ? "shadow-md agent-picker-active scale-[1.02]" : "hover:bg-white/95 hover:shadow-sm opacity-85 hover:opacity-100"
                }`}
                style={{
                  backgroundColor: active ? `${a.primary}14` : "rgba(255,255,255,0.7)",
                  borderColor: active ? a.primary : `${a.primary}22`,
                  ...(active
                    ? { backgroundImage: `linear-gradient(180deg, ${a.primary}12, ${a.accent}10, transparent)` }
                    : {}),
                }}
                title={`${a.label} — ${a.description}`}
                aria-pressed={active}
              >
                <div className="flex items-center justify-center h-10 w-10 shrink-0">
                  <AgentAvatar agent={a.id} size="xs" />
                </div>
                <span
                  className="mt-1.5 text-[11px] font-semibold leading-tight text-center w-full truncate"
                  style={{ color: active ? a.primary : "#374151" }}
                >
                  {SHORT[a.id] || a.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
