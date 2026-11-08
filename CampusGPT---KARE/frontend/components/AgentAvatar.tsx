"use client";

import { motion } from "framer-motion";
import type { AgentType } from "@/hooks/useChat";
import { getAgentTheme } from "@/lib/agentThemes";
import { CHARACTER_MAP } from "./agents/AgentCharacterArt";

type Props = {
  agent: AgentType;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  speaking?: boolean;
  className?: string;
  showPlatform?: boolean;
};

const SIZES = { xs: 36, sm: 56, md: 88, lg: 120, xl: 160 };

export default function AgentAvatar({ agent, size = "md", speaking = false, className = "", showPlatform = false }: Props) {
  const theme = getAgentTheme(agent);
  const px = SIZES[size];
  const Character = CHARACTER_MAP[agent];

  return (
    <motion.div
      className={`relative shrink-0 flex items-center justify-center overflow-visible ${className}`}
      style={{ width: px, height: px }}
      animate={speaking ? { scale: [1, 1.04, 1] } : { scale: 1 }}
      transition={{ duration: 0.6, repeat: speaking ? Infinity : 0 }}
    >
      {showPlatform && (
        <div
          className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[85%] h-[12%] rounded-[50%] agent-platform pointer-events-none"
          style={{ background: `radial-gradient(ellipse, ${theme.glow} 0%, transparent 70%)` }}
        />
      )}
      <div
        className="absolute inset-0 rounded-full agent-avatar-glow pointer-events-none"
        style={{ background: `radial-gradient(circle, ${theme.glow} 0%, transparent 70%)` }}
      />
      <svg
        viewBox="0 0 100 100"
        width={px}
        height={px}
        className="relative z-10 drop-shadow-lg block mx-auto"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden
      >
        <Character primary={theme.primary} secondary={theme.secondary} accent={theme.accent} />
      </svg>
      {speaking && (
        <motion.span className="absolute -right-1 -top-1 flex gap-0.5 items-end h-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="w-1 rounded-full self-end"
              style={{ backgroundColor: theme.primary }}
              animate={{ height: [4, 10, 4] }}
              transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.12 }}
            />
          ))}
        </motion.span>
      )}
    </motion.div>
  );
}
