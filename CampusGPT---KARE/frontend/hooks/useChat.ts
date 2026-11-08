"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { apiFetch, INTERNET_ISSUE_MESSAGE, userFacingError } from "@/lib/network";
import { apiGet } from "@/lib/api";
import { defaultAgentForRole, agentsForRole, isHostelAgent } from "@/lib/agentsByRole";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: { source?: string; excerpt?: string; relevance?: number; page?: number }[];
  confidence?: number;
  escalated?: boolean;
  diagram?: { explanation?: string; diagram?: string } | null;
  points_earned?: number;
  data_used?: { data: string; purpose: string; source: string; permission: string; access: string }[];
  kind?: string;
  pending_action?: { type: string; payload: Record<string, string> } | null;
  needs_confirmation?: boolean;
  id?: string;
}

export type AgentType = "general" | "admission" | "reception" | "hostel" | "warden" | "academic" | "faculty";

type SessionMap = Partial<Record<AgentType, string | null>>;

function detailToString(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: string }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return fallback;
}

export function useChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionMap, setSessionMap] = useState<SessionMap>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentType, setAgentTypeState] = useState<AgentType>("general");
  const agentTypeRef = useRef(agentType);
  const roleDefaulted = useRef(false);
  const requestAgentRef = useRef<AgentType | null>(null);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    agentTypeRef.current = agentType;
  }, [agentType]);

  useEffect(() => {
    if (!user?.role) return;
    const opts = {
      residenceType: user.residence_type,
      isHosteller: user.is_hosteller,
    };
    if (!roleDefaulted.current) {
      setAgentTypeState(defaultAgentForRole(user.role, opts));
      roleDefaulted.current = true;
      return;
    }
    // If residence loads later / student is not a hosteller, leave hostel desks
    const allowed = agentsForRole(user.role, opts).map((a) => a.id);
    if (!allowed.includes(agentTypeRef.current)) {
      setAgentTypeState((allowed[0] as AgentType) || "general");
      setMessages([]);
    }
  }, [user?.role, user?.residence_type, user?.is_hosteller]);

  const sessionId = sessionMap[agentType] ?? null;

  const setAgentType = useCallback(
    async (next: AgentType) => {
      if (next === agentTypeRef.current) return;
      // Block hostel/warden desks for day scholars and bus students
      if (
        user?.role === "student" &&
        isHostelAgent(next) &&
        user.is_hosteller !== true &&
        (user.residence_type || "").toLowerCase() !== "hostel"
      ) {
        setError("Hostel and Warden chats are only for hostellers.");
        return;
      }
      setAgentTypeState(next);
      setError(null);
      const nextSession = sessionMap[next];
      if (nextSession) {
        try {
          const data = await apiGet<{ messages: Message[]; agent_type?: string }>(
            `/api/chat/sessions/${nextSession}`
          );
          if (agentTypeRef.current === next || true) {
            setMessages(data.messages || []);
          }
          return;
        } catch {
          setSessionMap((m) => ({ ...m, [next]: null }));
        }
      }
      setMessages([]);
    },
    [sessionMap, user?.role, user?.is_hosteller, user?.residence_type]
  );

  const sendMessage = useCallback(
    async (content: string, agent: AgentType = agentType, onStatus?: (s: string) => void) => {
      if (!content.trim()) return;

      const forAgent = agent;
      const reqId = ++requestSeqRef.current;
      requestAgentRef.current = forAgent;
      const userMessage: Message = {
        role: "user",
        content: content.trim(),
        id: `u-${Date.now()}`,
      };

      // Only append to visible thread if this agent is currently selected
      if (agentTypeRef.current === forAgent) {
        setMessages((prev) => [...prev, userMessage]);
      }
      setLoading(true);
      setError(null);
      onStatus?.("Checking authorized records...");

      const activeSession = sessionMap[forAgent] ?? null;
      const history =
        agentTypeRef.current === forAgent
          ? messages.map((m) => ({ role: m.role, content: m.content }))
          : [];

      const controller = new AbortController();
      const timeoutMs = 90000;
      const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

      try {
        setTimeout(() => {
          if (requestSeqRef.current === reqId) onStatus?.("Searching university knowledge...");
        }, 400);
        const token = typeof window !== "undefined" ? localStorage.getItem("campus_gpt_token") : null;
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await apiFetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            message: content.trim(),
            session_id: activeSession,
            history: [...history, { role: "user", content: content.trim() }],
            agent_type: forAgent,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(detailToString(err.detail, res.statusText));
        }

        const data = await res.json();
        // Ignore stale responses if a newer send started
        if (requestSeqRef.current !== reqId) return;

        setSessionMap((m) => ({ ...m, [forAgent]: data.session_id }));

        const assistantMessage: Message = {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          confidence: data.confidence,
          escalated: data.escalated,
          diagram: data.diagram ?? null,
          points_earned: data.points_earned,
          data_used: data.data_used || [],
          kind: data.kind,
          pending_action: data.pending_action || null,
          needs_confirmation: !!data.needs_confirmation,
          id: `a-${Date.now()}`,
        };

        // Drop reply if user switched agents mid-flight
        if (agentTypeRef.current === forAgent) {
          setMessages((prev) => [...prev, assistantMessage]);
        }
      } catch (e) {
        if (requestSeqRef.current !== reqId) return;
        const aborted = e instanceof DOMException && e.name === "AbortError";
        const msg = aborted
          ? "The reply took too long. Please try again."
          : userFacingError(e, "Failed to get response");
        if (agentTypeRef.current === forAgent) {
          setError(msg);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content:
                msg === INTERNET_ISSUE_MESSAGE
                  ? INTERNET_ISSUE_MESSAGE
                  : aborted
                    ? msg
                    : "Sorry, I couldn't process your request. Please try again.",
              id: `e-${Date.now()}`,
            },
          ]);
        }
      } finally {
        window.clearTimeout(timeoutId);
        // Always clear loading for the latest in-flight request
        if (requestSeqRef.current === reqId) {
          setLoading(false);
          onStatus?.("");
        }
      }
    },
    [messages, sessionMap, agentType]
  );

  const loadSession = useCallback(async (id: string) => {
    const data = await apiGet<{ messages: Message[]; agent_type?: string }>(`/api/chat/sessions/${id}`);
    const at = (data.agent_type as AgentType | undefined) || agentTypeRef.current;
    if (data.agent_type && data.agent_type !== agentTypeRef.current) {
      setAgentTypeState(at);
    }
    setSessionMap((m) => ({ ...m, [at]: id }));
    setMessages(data.messages || []);
    setError(null);
  }, []);

  const clearChat = useCallback(async () => {
    const current = sessionMap[agentType];
    setMessages([]);
    setSessionMap((m) => ({ ...m, [agentType]: null }));
    setError(null);
    if (current) {
      try {
        const { apiDelete } = await import("@/lib/api");
        await apiDelete(`/api/chat/sessions/${current}`);
      } catch {
        // local clear still succeeds
      }
    }
  }, [sessionMap, agentType]);

  const clearAllHistory = useCallback(async () => {
    setMessages([]);
    setSessionMap({});
    setError(null);
    try {
      const { apiDelete } = await import("@/lib/api");
      await apiDelete("/api/chat/sessions");
    } catch {
      // ignore
    }
  }, []);

  const confirmPendingAction = useCallback(
    async (action: { type: string; payload: Record<string, string> }, messageIdOrIndex: string | number) => {
      setLoading(true);
      setError(null);
      try {
        const { apiPost } = await import("@/lib/api");
        const res = await apiPost<{ answer?: string; ok?: boolean }>("/api/actions/confirm", {
          type: action.type,
          payload: action.payload,
        });
        setMessages((prev) => {
          const next = [...prev];
          const idx =
            typeof messageIdOrIndex === "number"
              ? messageIdOrIndex
              : next.findIndex((m) => m.id === messageIdOrIndex);
          if (idx >= 0 && next[idx]) {
            next[idx] = {
              ...next[idx],
              needs_confirmation: false,
              pending_action: null,
            };
          }
          next.push({
            role: "assistant",
            content: res.answer || "Action completed and saved to KARE UIS.",
            id: `c-${Date.now()}`,
          });
          return next;
        });
      } catch (e) {
        setError(userFacingError(e, "Could not confirm action"));
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const dismissPendingAction = useCallback((messageIdOrIndex: string | number) => {
    setMessages((prev) => {
      const next = [...prev];
      const idx =
        typeof messageIdOrIndex === "number"
          ? messageIdOrIndex
          : next.findIndex((m) => m.id === messageIdOrIndex);
      if (idx >= 0 && next[idx]) {
        const kind = next[idx].pending_action?.type || "action";
        const note =
          kind === "apply_leave"
            ? "\n\n(Cancelled — leave was not submitted.)"
            : "\n\n(Cancelled — action was not submitted.)";
        next[idx] = {
          ...next[idx],
          needs_confirmation: false,
          pending_action: null,
          content: (next[idx].content || "") + note,
        };
      }
      return next;
    });
  }, []);

  return {
    messages,
    loading,
    error,
    sendMessage,
    clearChat,
    clearAllHistory,
    confirmPendingAction,
    dismissPendingAction,
    agentType,
    setAgentType,
    sessionId,
    loadSession,
  };
}
