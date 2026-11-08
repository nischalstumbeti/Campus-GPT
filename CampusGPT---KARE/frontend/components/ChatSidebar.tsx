"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, MessageSquarePlus, PanelLeftClose, PanelLeft, Trash2 } from "lucide-react";
import { apiDelete, apiGet } from "@/lib/api";

export type Discussion = { session_id: string; title: string; updated_at: string | null };
export type MemoryFact = { id: number; fact: string; created_at: string | null };

export default function ChatSidebar({
  currentSessionId,
  refreshKey,
  onNewChat,
  onClearAll,
  onOpenSession,
  agentType,
}: {
  currentSessionId: string | null;
  refreshKey: number;
  onNewChat: () => void;
  onClearAll?: () => void | Promise<void>;
  onOpenSession: (id: string) => void;
  agentType?: string;
}) {
  const [open, setOpen] = useState(true);
  const [sessions, setSessions] = useState<Discussion[]>([]);
  const [memories, setMemories] = useState<MemoryFact[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const q = agentType ? `?agent_type=${encodeURIComponent(agentType)}` : "";
    apiGet<{ sessions: Discussion[]; memories: MemoryFact[] }>(`/api/chat/sessions${q}`)
      .then((d) => {
        setSessions(d.sessions || []);
        setMemories(d.memories || []);
      })
      .catch(() => {
        setSessions([]);
        setMemories([]);
      });
  }, [agentType]);

  useEffect(() => {
    load();
  }, [load, refreshKey, currentSessionId, agentType]);

  const removeSession = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setBusy(true);
    try {
      await apiDelete(`/api/chat/sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (id === currentSessionId) onNewChat();
      load();
    } catch {
      load();
    } finally {
      setBusy(false);
    }
  };

  const clearAll = async () => {
    if (!sessions.length) return;
    if (!window.confirm("Delete all chat history?")) return;
    setBusy(true);
    try {
      await apiDelete("/api/chat/sessions");
      setSessions([]);
      if (onClearAll) await onClearAll();
      else onNewChat();
      load();
    } catch {
      load();
    } finally {
      setBusy(false);
    }
  };

  const removeMemory = async (id: number) => {
    try {
      await apiDelete(`/api/chat/memory/${id}`);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch {
      load();
    }
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="shrink-0 w-11 h-full border-r border-[#7C5AED]/10 bg-white/95 flex flex-col items-center pt-3 gap-2 text-primary"
          title="Show discussions"
        >
          <PanelLeft className="w-4 h-4" />
          <Brain className="w-4 h-4" />
        </button>
      )}
      <aside
        className={`${
          open ? "flex" : "hidden"
        } w-[280px] shrink-0 flex-col border-r border-[#7C5AED]/10 bg-white/95 h-full`}
      >
        <div className="p-3 border-b border-gray-100 flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-primary">Discussions</p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onNewChat}
              className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-primary text-white hover:bg-primary/90"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" />
              New
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100"
              title="Hide sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>
        </div>
        {sessions.length > 0 && (
          <div className="px-3 py-2 border-b border-gray-50">
            <button
              type="button"
              disabled={busy}
              onClick={clearAll}
              className="text-[11px] text-red-600 hover:underline disabled:opacity-50"
            >
              Delete all history
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.length === 0 && (
            <p className="text-xs text-gray-500 px-2 py-6 text-center">
              No saved discussions yet. Start chatting to keep them here.
            </p>
          )}
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className={`w-full group rounded-xl px-3 py-2.5 text-sm transition-colors flex items-start justify-between gap-2 ${
                currentSessionId === s.session_id
                  ? "bg-primary/10 text-primary"
                  : "hover:bg-gray-50 text-gray-800"
              }`}
            >
              <button
                type="button"
                onClick={() => onOpenSession(s.session_id)}
                className="text-left flex-1 min-w-0"
              >
                <span className="line-clamp-2 font-medium leading-snug block">{s.title}</span>
              </button>
              <button
                type="button"
                aria-label="Delete discussion"
                disabled={busy}
                onClick={(e) => removeSession(s.session_id, e)}
                className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 shrink-0 disabled:opacity-40"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
        <div className="border-t border-gray-100 p-3 max-h-[42%] overflow-y-auto">
          <div className="flex items-center gap-1.5 mb-2">
            <Brain className="w-4 h-4 text-primary" />
            <p className="text-sm font-semibold text-primary">Long-term memory</p>
          </div>
          <p className="text-[11px] text-gray-500 mb-2">Kept across chats. Say “remember that…” to add more.</p>
          {memories.length === 0 && <p className="text-xs text-gray-400">Nothing stored yet.</p>}
          <ul className="space-y-2">
            {memories.map((m) => (
              <li key={m.id} className="group rounded-lg bg-primary/5 px-2.5 py-2 text-xs text-gray-700 flex gap-2">
                <span className="flex-1 leading-snug">{m.fact}</span>
                <button
                  type="button"
                  onClick={() => removeMemory(m.id)}
                  className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600"
                  title="Forget"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}
