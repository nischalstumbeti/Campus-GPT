"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Mic, MicOff, Trash2, FileText, ChevronDown, ChevronRight, Volume2, Loader2 } from "lucide-react";
import { useChat, type AgentType } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import { apiFetch } from "@/lib/network";
import { getAgentTheme } from "@/lib/agentThemes";
import { agentsForRole } from "@/lib/agentsByRole";
import { useAuth } from "@/hooks/useAuth";
import ChatSidebar from "./ChatSidebar";
import MermaidDiagram from "./MermaidDiagram";
import AgentAvatar from "./AgentAvatar";
import AgentThemeBackground from "./AgentThemeBackground";
import AgentWelcomeScene from "./AgentWelcomeScene";
import AgentPickerStrip from "./AgentPickerStrip";
import { renderMessageContent } from "./ChatTable";

function SourcesAccordion({ sources }: { sources: { source?: string; excerpt?: string; relevance?: number; page?: number }[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        <FileText className="w-3.5 h-3.5" />
        Sources ({sources.length})
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((s, j) => (
            <div key={j} className="rounded-lg bg-gray-50 px-3 py-2 text-xs">
              <p className="font-medium text-gray-700">{s.source || "Knowledge base"}</p>
              {s.page && <span className="text-gray-500">Page {s.page}</span>}
              {s.relevance != null && (
                <span className="text-gray-500 ml-2">{Math.round(s.relevance * 100)}% match</span>
              )}
              {s.excerpt && <p className="mt-1 text-gray-600 line-clamp-2">{s.excerpt}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const UNIFIED_QUERIES = [
  "What is my attendance?",
  "Am I eligible for exams?",
  "How many classes to reach 75%?",
  "What credits do I have remaining?",
  "Show my timetable",
  "Draft a bonafide letter",
  "Hostel leave status",
  "What are the attendance regulations?",
];

const COMMON_QUERIES: Record<AgentType, string[]> = {
  general: UNIFIED_QUERIES,
  academic: [
    "What courses am I enrolled in this semester?",
    "Show my internal marks",
    "What is the exam timetable?",
    "What are the attendance regulations?",
    "How many classes do I need to reach 75%?",
  ],
  faculty: [
    "What classes do I teach today?",
    "Show my office hours",
    "Any department circulars?",
    "How do I enter internal marks?",
  ],
  admission: [
    "What programs are offered?",
    "What is the application fee?",
    "Am I eligible for B.Tech CSE?",
    "What documents are required?",
    "What scholarships are available?",
  ],
  reception: [
    "Tell me about KARE university",
    "Where is the examination branch?",
    "Department contact numbers and emails",
    "What programs and facilities are available?",
    "Admission process and documents needed",
    "Hostel, fees, and placement overview",
  ],
  hostel: [
    "What is the hostel availability?",
    "How do I apply for a room?",
    "What facilities do hostels have?",
    "What is the hostel fee structure?",
    "Apply for hostel leave",
  ],
  warden: [
    "Apply for hostel leave",
    "What are the hostel rules?",
    "Who do I report a complaint to?",
    "Emergency contact for the hostel?",
  ],
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

function SpeakButton({ text, className, color }: { text: string; className?: string; color?: string }) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handleSpeak = async () => {
    if (!text.trim() || loading || playing) return;
    setLoading(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim().slice(0, 5000) }),
      });
      if (!res.ok) throw new Error("TTS failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setPlaying(false);
        URL.revokeObjectURL(url);
      };
      audio.onplay = () => setPlaying(true);
      await audio.play();
    } catch {
      setLoading(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleSpeak}
      disabled={loading || !text.trim()}
      className={`p-1.5 rounded-lg hover:bg-black/5 transition-colors disabled:opacity-50 ${className || ""}`}
      style={color ? { color } : undefined}
      title="Listen (Indian English voice)"
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Volume2 className="w-4 h-4" />}
    </button>
  );
}

export default function ChatInterface() {
  const { messages, loading, error, sendMessage, clearChat, clearAllHistory, confirmPendingAction, dismissPendingAction, agentType, setAgentType, sessionId, loadSession } =
    useChat();
  const { user } = useAuth();
  const agentOptions = agentsForRole(user?.role, {
    residenceType: user?.residence_type,
    isHosteller: user?.is_hosteller,
  });
  const [input, setInput] = useState("");
  const [loadingStatus, setLoadingStatus] = useState("");
  const [points, setPoints] = useState<number | null>(null);
  const [historyTick, setHistoryTick] = useState(0);
  const [showAgents, setShowAgents] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const agentsRef = useRef<HTMLDivElement>(null);
  const agentToggleRef = useRef<HTMLButtonElement>(null);

  const theme = getAgentTheme(agentType);

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("campus_gpt_token") : null;
    if (token) {
      apiFetch(`${API_BASE}/api/student/points`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.json())
        .then((d) => setPoints(d.points ?? 0))
        .catch(() => setPoints(null));
    } else {
      setPoints(null);
    }
  }, [messages]);

  const { recording, error: voiceError, startRecording, stopRecording } = useVoice((text) => {
    setInput((prev) => (prev ? `${prev} ${text}` : text));
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !loading) {
      sendMessage(input, agentType, setLoadingStatus);
      setInput("");
    }
  };

  const handleQuickQuery = (query: string) => {
    if (!loading) sendMessage(query, agentType, setLoadingStatus);
  };

  const pickAgent = (id: AgentType) => {
    void setAgentType(id);
    setShowAgents(false);
    setHistoryTick((t) => t + 1);
  };

  const openAgentMenu = () => setShowAgents(true);
  const closeAgentMenu = () => setShowAgents(false);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (agentsRef.current && !agentsRef.current.contains(e.target as Node)) {
        setShowAgents(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowAgents(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <div className="flex h-full min-h-0">
      <ChatSidebar
        currentSessionId={sessionId}
        refreshKey={historyTick + messages.length}
        agentType={agentType}
        onNewChat={async () => {
          await clearChat();
          setHistoryTick((t) => t + 1);
        }}
        onClearAll={async () => {
          await clearAllHistory();
          setHistoryTick((t) => t + 1);
        }}
        onOpenSession={(id) => {
          loadSession(id).catch(() => null);
        }}
      />
      <div className="relative flex flex-col h-full min-h-0 min-w-0 flex-1">
        <AgentThemeBackground agent={agentType} />

        <div
          className="relative z-20 flex items-center justify-between px-4 sm:px-6 py-3 border-b backdrop-blur-md transition-colors duration-500 shrink-0 overflow-visible"
          style={{ borderColor: `${theme.primary}22`, backgroundColor: "rgba(255,255,255,0.82)" }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center justify-center w-14 h-14 shrink-0">
              <AgentAvatar agent={agentType} size="sm" speaking={loading} />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wider truncate" style={{ color: theme.secondary }}>
                {theme.roleTitle}
              </p>
              <h2 className="font-semibold truncate leading-tight" style={{ color: theme.primary }}>
                {theme.label}
              </h2>
              <p className="text-xs text-gray-500 truncate">
                {theme.tagline}
                {points !== null && <span className="ml-2 font-medium" style={{ color: theme.primary }}>· {points} pts</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="relative" ref={agentsRef}>
              <button
                ref={agentToggleRef}
                type="button"
                onClick={() => (showAgents ? closeAgentMenu() : openAgentMenu())}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors"
                style={{ backgroundColor: `${theme.primary}18`, color: theme.primary }}
                aria-expanded={showAgents}
                aria-haspopup="listbox"
              >
                Switch agent
                <ChevronDown className={`w-4 h-4 transition-transform ${showAgents ? "rotate-180" : ""}`} />
              </button>
              {showAgents && (
                <div
                  className="absolute right-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-2xl border bg-white/95 backdrop-blur-md shadow-2xl"
                  style={{ borderColor: `${theme.primary}30`, boxShadow: `0 18px 45px -12px ${theme.glow}` }}
                >
                  <p className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider text-gray-400 bg-gray-50/80 border-b">
                    Choose an assistant
                  </p>
                  <div className="max-h-[60vh] overflow-y-auto py-1">
                    {agentOptions.map((a) => {
                      const active = agentType === a.id;
                      return (
                        <button
                          key={a.id}
                          type="button"
                          onClick={() => pickAgent(a.id)}
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${
                            active ? "font-semibold" : "hover:bg-black/5"
                          }`}
                          style={active ? { color: a.primary, backgroundColor: `${a.primary}12` } : { color: "#111827" }}
                        >
                          <AgentAvatar agent={a.id} size="xs" />
                          <span className="min-w-0">
                            <span className="block truncate">{a.label}</span>
                            <span className="block truncate text-[11px] font-normal opacity-60">{a.roleTitle}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={async () => {
                await clearChat();
                setHistoryTick((t) => t + 1);
              }}
              className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-red-600 transition-colors"
              title="Clear chat"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>
        </div>

        <AgentPickerStrip agent={agentType} onSelect={pickAgent} agents={agentOptions} />

        <div className="relative z-10 flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <AgentWelcomeScene
              agent={agentType}
              loading={loading}
              onQuickQuery={handleQuickQuery}
              queries={COMMON_QUERIES[agentType]}
            />
          )}

          <AnimatePresence>
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {m.role === "assistant" && (
                  <div className="shrink-0 pt-1">
                    <AgentAvatar agent={agentType} size="sm" speaking={loading && i === messages.length - 1} />
                  </div>
                )}
                <div
                  className={`max-w-[82%] rounded-2xl px-4 py-3 shadow-sm ${
                    m.role === "user" ? "rounded-br-md text-white" : `rounded-bl-md border ${theme.bubble}`
                  }`}
                  style={m.role === "user" ? { backgroundColor: theme.primary } : undefined}
                >
                  {m.role === "assistant" && m.points_earned !== undefined && m.points_earned > 0 && (
                    <p className="text-xs text-green-600 font-medium mb-2">+{m.points_earned} pts earned</p>
                  )}
                  {m.role === "assistant" && m.diagram?.diagram && (
                    <div className="mb-3">
                      {m.diagram.explanation && (
                        <p className="text-sm text-gray-600 mb-2">{m.diagram.explanation}</p>
                      )}
                      <MermaidDiagram chart={m.diagram.diagram} title="Process Diagram" />
                    </div>
                  )}
                  {m.role === "assistant" ? renderMessageContent(m.content) : (
                    <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                  )}
                  {m.role === "assistant" && m.needs_confirmation && m.pending_action && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={loading}
                        onClick={() => confirmPendingAction(m.pending_action!, i)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white"
                        style={{ backgroundColor: theme.primary }}
                      >
                        Confirm & submit to UIS
                      </button>
                      <button
                        type="button"
                        disabled={loading}
                        onClick={() => dismissPendingAction(i)}
                        className="px-3 py-1.5 rounded-lg text-xs border border-gray-200 text-gray-600"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                    <SourcesAccordion sources={m.sources} />
                  )}
                  {m.role === "assistant" && m.data_used && m.data_used.length > 0 && (
                    <details className="mt-2 text-xs text-gray-600">
                      <summary className="cursor-pointer" style={{ color: theme.primary }}>
                        Why was this information used?
                      </summary>
                      <ul className="mt-1 space-y-1">
                        {m.data_used.map((d, j) => (
                          <li key={j}>
                            Data: {d.data} · Purpose: {d.purpose} · Source: {d.source} · Permission: {d.permission}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {m.role === "assistant" && m.escalated && (
                    <p className="mt-2 text-xs text-amber-600">
                      This query was flagged for human review due to low confidence.
                    </p>
                  )}
                  {m.role === "assistant" && m.content && (
                    <div className="mt-2 pt-2 border-t border-gray-100 flex items-center gap-2">
                      <SpeakButton text={m.content} color={theme.primary} />
                      <span className="text-xs text-gray-500">Listen</span>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && messages.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-2 justify-start">
              <div className="shrink-0 pt-1">
                <AgentAvatar agent={agentType} size="sm" speaking />
              </div>
              <div className={`rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border ${theme.bubble}`}>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <span className="typing-dot w-2 h-2 rounded-full" style={{ backgroundColor: theme.primary }} />
                    <span className="typing-dot w-2 h-2 rounded-full" style={{ backgroundColor: theme.primary }} />
                    <span className="typing-dot w-2 h-2 rounded-full" style={{ backgroundColor: theme.primary }} />
                  </div>
                  {loadingStatus && (
                    <span className="text-xs text-gray-500 animate-pulse">{loadingStatus}</span>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {(error || voiceError) && (
            <p className="text-sm text-red-600 text-center">{error || voiceError}</p>
          )}

          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={handleSubmit}
          className="relative z-30 shrink-0 p-4 border-t backdrop-blur-md transition-colors duration-500"
          style={{ borderColor: `${theme.primary}22`, backgroundColor: "rgba(255,255,255,0.88)" }}
          onClick={() => inputRef.current?.focus()}
        >
          {messages.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-center mb-3 max-w-3xl mx-auto">
              {COMMON_QUERIES[agentType].slice(0, 4).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => handleQuickQuery(q)}
                  disabled={loading}
                  className="px-2.5 py-1 rounded-lg text-xs transition-colors disabled:opacity-50"
                  style={{ backgroundColor: `${theme.primary}10`, color: theme.primary }}
                >
                  {q}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2 sm:gap-3 items-end max-w-3xl mx-auto">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!loading && input.trim()) handleSubmit(e);
                }
              }}
              placeholder={loading ? "Waiting for reply… you can still type the next question" : `Ask ${theme.label.toLowerCase()}...`}
              rows={1}
              className="flex-1 min-w-0 rounded-xl border px-4 py-3 resize-none focus:outline-none focus:ring-2 bg-white/90 relative z-20"
              style={{ borderColor: `${theme.primary}40`, outlineColor: theme.primary }}
              // Keep input clickable while a reply is loading (only Send is blocked)
              aria-busy={loading}
            />
            <button
              type="button"
              onClick={recording ? stopRecording : startRecording}
              className={`shrink-0 p-3 rounded-xl border transition-colors relative z-20 ${
                recording
                  ? "bg-red-500 text-white border-red-500"
                  : "bg-white/90 text-gray-600 hover:bg-gray-100"
              }`}
              style={{ borderColor: recording ? undefined : `${theme.primary}30` }}
              title={recording ? "Stop recording" : "Voice input"}
              aria-label={recording ? "Stop recording" : "Voice input"}
            >
              {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send message"
              className="shrink-0 p-3 rounded-xl text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md relative z-20"
              style={{ backgroundColor: theme.primary }}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
