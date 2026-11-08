"use client";

import { motion } from "framer-motion";
import type { AgentType } from "@/hooks/useChat";
import { getAgentTheme } from "@/lib/agentThemes";
import AgentAvatar from "./AgentAvatar";
import AgentEnvironmentArt from "./agents/AgentEnvironmentArt";

export default function AgentWelcomeScene({
  agent,
  loading,
  onQuickQuery,
  queries,
}: {
  agent: AgentType;
  loading: boolean;
  onQuickQuery: (q: string) => void;
  queries: string[];
}) {
  const theme = getAgentTheme(agent);

  return (
    <motion.div
      key={agent}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="flex flex-col items-center justify-center h-full min-h-[320px] px-2 py-4"
    >
      <div
        className="relative w-full max-w-xl rounded-3xl border shadow-xl overflow-hidden agent-welcome-card"
        style={{
          borderColor: `${theme.primary}25`,
          background: `linear-gradient(160deg, rgba(255,255,255,0.92) 0%, ${theme.surface}cc 100%)`,
          boxShadow: `0 20px 50px -12px ${theme.glow}`,
        }}
      >
        <div className="absolute inset-x-0 bottom-0 h-[38%] opacity-80">
          <AgentEnvironmentArt
            agent={agent}
            primary={theme.primary}
            secondary={theme.secondary}
            accent={theme.accent}
            compact
          />
        </div>

        <div className="relative z-10 px-6 pt-6 pb-5 text-center flex flex-col items-center">
          <div className="flex items-center justify-center h-40 w-40 mb-3">
            <AgentAvatar agent={agent} size="xl" speaking={loading} showPlatform />
          </div>

          <span
            className="inline-block px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider mb-2"
            style={{ backgroundColor: `${theme.primary}15`, color: theme.primary }}
          >
            {theme.roleTitle}
          </span>

          <h3 className="text-xl sm:text-2xl font-bold mb-1" style={{ color: theme.primary }}>
            {theme.label}
          </h3>
          <p className="text-gray-600 text-sm max-w-md mx-auto leading-relaxed mb-1">{theme.description}</p>
          <p className="text-xs font-medium mb-5" style={{ color: theme.secondary }}>
            {theme.envName} · Kalasalingam University
          </p>

          <div className="flex flex-wrap gap-2 justify-center content-center">
            {queries.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onQuickQuery(q)}
                disabled={loading}
                className="px-3 py-1.5 rounded-full text-xs font-medium transition-all disabled:opacity-50 border hover:scale-[1.02] active:scale-[0.98]"
                style={{
                  backgroundColor: `${theme.primary}10`,
                  color: theme.primary,
                  borderColor: `${theme.primary}28`,
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
