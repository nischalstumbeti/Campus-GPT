import type { AgentType } from "@/hooks/useChat";
import { AGENT_LIST, type AgentTheme } from "@/lib/agentThemes";

export type ResidenceType = "hostel" | "day_scholar" | "bus" | string;

const HOSTEL_ONLY_AGENTS: AgentType[] = ["hostel", "warden"];

export type AgentFilterOpts = {
  residenceType?: ResidenceType | null;
  isHosteller?: boolean | null;
};

function isStudentRole(role?: string | null): boolean {
  const r = (role || "student").toLowerCase();
  return r === "student" || r === "";
}

function isHosteller(opts?: AgentFilterOpts): boolean {
  if (opts?.isHosteller === true) return true;
  return (opts?.residenceType || "").toLowerCase() === "hostel";
}

/** True once we know the student is NOT a hosteller (day scholar / bus). */
function isConfirmedNonHosteller(opts?: AgentFilterOpts): boolean {
  if (opts?.isHosteller === true) return false;
  const res = (opts?.residenceType || "").toLowerCase();
  if (res === "hostel") return false;
  if (opts?.isHosteller === false) return true;
  if (res === "day_scholar" || res === "bus") return true;
  return false;
}

/** Hierarchy + residence: only hostellers see Hostel / Warden desks. */
export function agentsForRole(role?: string | null, opts?: AgentFilterOpts): AgentTheme[] {
  const r = (role || "student").toLowerCase();
  let list: AgentTheme[];

  if (r === "admin" || r === "super_admin") {
    list = AGENT_LIST.filter((a) =>
      ["general", "academic", "faculty", "admission", "reception"].includes(a.id)
    );
  } else if (r === "faculty" || r === "hostel_admin" || r === "hostel_warden") {
    list = AGENT_LIST.filter((a) =>
      ["general", "academic", "admission", "reception"].includes(a.id)
    );
  } else {
    list = [...AGENT_LIST];
  }

  // Day scholars and bus students must not see Hostel / Warden chats
  if (isStudentRole(r) && isConfirmedNonHosteller(opts)) {
    list = list.filter((a) => !HOSTEL_ONLY_AGENTS.includes(a.id));
  }

  return list;
}

export function defaultAgentForRole(role?: string | null, opts?: AgentFilterOpts): AgentType {
  const list = agentsForRole(role, opts);
  return (list[0]?.id as AgentType) || "general";
}

export function isHostelAgent(id: AgentType | string): boolean {
  return HOSTEL_ONLY_AGENTS.includes(id as AgentType);
}
