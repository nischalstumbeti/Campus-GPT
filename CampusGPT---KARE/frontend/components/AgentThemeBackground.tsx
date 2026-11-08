"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { AgentType } from "@/hooks/useChat";
import { getAgentTheme } from "@/lib/agentThemes";
import AgentEnvironmentArt from "./agents/AgentEnvironmentArt";

export default function AgentThemeBackground({ agent }: { agent: AgentType }) {
  const theme = getAgentTheme(agent);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0" aria-hidden>
      <AnimatePresence mode="wait">
        <motion.div
          key={agent}
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="absolute inset-0"
          style={{
            background: `linear-gradient(165deg, ${theme.bgFrom} 0%, ${theme.bgVia} 42%, ${theme.bgTo} 100%)`,
          }}
        />
      </AnimatePresence>

      <motion.div
        key={`orb1-${agent}`}
        className="absolute rounded-full blur-3xl agent-bg-orb"
        style={{ width: 320, height: 320, top: "-10%", right: "-8%", background: theme.glow }}
        animate={{ x: [0, 24, 0], y: [0, 18, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        key={`orb2-${agent}`}
        className="absolute rounded-full blur-3xl agent-bg-orb"
        style={{ width: 260, height: 260, bottom: "8%", left: "-6%", background: theme.glow, opacity: 0.65 }}
        animate={{ x: [0, -18, 0], y: [0, -12, 0] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="absolute inset-0 agent-bg-grid opacity-[0.035]" style={{ color: theme.primary }} />

      <div className="absolute inset-x-0 bottom-0 h-[45%] min-h-[140px] max-h-[280px]">
        <AgentEnvironmentArt agent={agent} primary={theme.primary} secondary={theme.secondary} accent={theme.accent} />
      </div>

      <div
        className="absolute top-4 left-4 px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-wide uppercase agent-env-badge"
        style={{ backgroundColor: `${theme.primary}14`, color: theme.primary, border: `1px solid ${theme.primary}25` }}
      >
        {theme.envName}
      </div>

      <motion.div
        key={`deco-${agent}`}
        className="absolute top-[20%] right-[8%] w-16 h-16 rounded-2xl agent-float-slow opacity-[0.12]"
        style={{ background: `linear-gradient(135deg, ${theme.accent}, ${theme.primary})` }}
      />
      <motion.div
        key={`deco2-${agent}`}
        className="absolute top-[35%] left-[6%] w-10 h-10 rounded-full agent-float-delay opacity-[0.1]"
        style={{ background: theme.accent }}
      />
    </div>
  );
}
