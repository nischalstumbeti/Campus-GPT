"use client";

import type { ComponentType } from "react";
import { motion } from "framer-motion";
import type { AgentType } from "@/hooks/useChat";

type EProps = { primary: string; secondary: string; accent: string };

function CampusScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="120" width="400" height="80" fill="#86EFAC" opacity="0.35" />
      <rect x="0" y="155" width="400" height="45" fill="#D4A574" opacity="0.25" />
      <motion.g className="agent-drift-slow" animate={{ x: [0, 6, 0] }}>
        <rect x="40" y="70" width="90" height="55" rx="4" fill={primary} opacity="0.35" />
        <polygon points="40,70 85,42 130,70" fill={secondary} opacity="0.4" />
        <rect x="55" y="85" width="14" height="18" fill={accent} opacity="0.5" />
        <rect x="78" y="85" width="14" height="18" fill={accent} opacity="0.5" />
        <rect x="101" y="85" width="14" height="18" fill={accent} opacity="0.5" />
      </motion.g>
      <motion.g className="agent-drift-delay" animate={{ x: [0, -5, 0] }}>
        <rect x="250" y="78" width="70" height="48" rx="3" fill={secondary} opacity="0.3" />
        <polygon points="250,78 285,55 320,78" fill={primary} opacity="0.35" />
      </motion.g>
      <rect x="170" y="130" width="60" height="35" rx="3" fill="white" opacity="0.5" stroke={primary} strokeWidth="1" />
      <text x="200" y="150" textAnchor="middle" fontSize="7" fill={primary} fontWeight="bold">NOTICE</text>
      <circle cx="320" cy="145" r="8" fill="#22C55E" opacity="0.4" />
      <rect cx="300" cy="140" x="300" y="140" width="6" height="14" fill="#854D0E" opacity="0.35" rx="1" />
      <motion.circle cx="180" cy="168" r="5" fill={accent} opacity="0.4" animate={{ cx: [175, 185, 175] }} transition={{ duration: 8, repeat: Infinity }} />
      <motion.circle cx="220" cy="170" r="4" fill={accent} opacity="0.35" animate={{ cx: [215, 225, 215] }} transition={{ duration: 7, repeat: Infinity, delay: 1 }} />
    </g>
  );
}

function ClassroomScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="100" width="400" height="100" fill="#E5E7EB" opacity="0.4" />
      <rect x="20" y="40" width="160" height="70" rx="4" fill="white" opacity="0.7" stroke={primary} strokeWidth="1.5" />
      <text x="35" y="58" fontSize="6" fill={secondary}>f(x) = ax² + bx + c</text>
      <line x1="30" y1="65" x2="170" y2="65" stroke={accent} strokeWidth="1" opacity="0.5" />
      <line x1="30" y1="75" x2="150" y2="75" stroke={accent} strokeWidth="1" opacity="0.5" />
      <rect x="200" y="130" width="50" height="30" rx="2" fill="#D97706" opacity="0.35" />
      <rect x="260" y="130" width="50" height="30" rx="2" fill="#D97706" opacity="0.35" />
      <rect x="320" y="130" width="50" height="30" rx="2" fill="#D97706" opacity="0.35" />
      <motion.g animate={{ y: [0, -2, 0] }} transition={{ duration: 3, repeat: Infinity }}>
        <rect x="280" y="55" width="28" height="20" rx="2" fill="#374151" opacity="0.5" />
        <rect x="283" y="58" width="22" height="13" rx="1" fill={accent} opacity="0.6" />
      </motion.g>
      <rect x="30" y="130" width="12" height="16" rx="1" fill={primary} opacity="0.4" />
      <rect x="48" y="128" width="10" height="18" rx="1" fill={secondary} opacity="0.35" />
    </g>
  );
}

function FacultyOfficeScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="110" width="400" height="90" fill="#D6D3D1" opacity="0.3" />
      <rect x="30" y="125" width="140" height="12" rx="2" fill="#78716C" opacity="0.4" />
      <rect x="35" y="100" width="50" height="28" rx="2" fill="#374151" opacity="0.45" />
      <rect x="38" y="104" width="44" height="18" rx="1" fill={accent} opacity="0.5" />
      <rect x="100" y="95" width="35" height="45" rx="2" fill={primary} opacity="0.3" />
      <rect x="105" y="100" width="8" height="35" fill="white" opacity="0.4" />
      <rect x="118" y="100" width="8" height="35" fill="white" opacity="0.4" />
      <rect x="200" y="60" width="100" height="55" rx="3" fill="white" opacity="0.55" stroke={primary} strokeWidth="1" />
      <text x="215" y="78" fontSize="6" fill={secondary} fontWeight="bold">DEPT NOTICE</text>
      <line x1="210" y1="85" x2="290" y2="85" stroke={accent} strokeWidth="0.8" />
      <line x1="210" y1="93" x2="275" y2="93" stroke={accent} strokeWidth="0.8" />
      <rect x="280" y="125" width="60" height="40" rx="2" fill="#A8A29E" opacity="0.35" />
    </g>
  );
}

function AdmissionsScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="115" width="400" height="85" fill="#FED7AA" opacity="0.25" />
      <rect x="40" y="100" width="120" height="55" rx="4" fill="white" opacity="0.6" stroke={primary} strokeWidth="1.5" />
      <text x="55" y="118" fontSize="8" fill={primary} fontWeight="bold">ADMISSIONS</text>
      <rect x="55" y="125" width="35" height="22" rx="2" fill={accent} opacity="0.4" />
      <rect x="95" y="125" width="35" height="22" rx="2" fill={accent} opacity="0.35" />
      <motion.g animate={{ y: [0, -3, 0] }} transition={{ duration: 2.5, repeat: Infinity }}>
        <rect x="220" y="70" width="45" height="32" rx="2" fill="white" opacity="0.5" stroke={secondary} strokeWidth="1" />
        <circle cx="242" cy="82" r="8" fill={primary} opacity="0.3" />
      </motion.g>
      <rect x="300" y="105" width="30" height="40" rx="2" fill={primary} opacity="0.3" />
      <rect x="305" y="110" width="20" height="3" fill="white" opacity="0.5" />
      <rect x="305" y="116" width="20" height="3" fill="white" opacity="0.5" />
      <rect x="305" y="122" width="20" height="3" fill="white" opacity="0.5" />
    </g>
  );
}

function ReceptionScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="120" width="400" height="80" fill="#E0F2FE" opacity="0.35" />
      <rect x="50" y="105" width="180" height="45" rx="6" fill={primary} opacity="0.35" />
      <rect x="60" y="112" width="160" height="8" rx="2" fill="white" opacity="0.4" />
      <text x="140" y="135" textAnchor="middle" fontSize="8" fill="white" fontWeight="bold">RECEPTION</text>
      <rect x="280" y="130" width="40" height="35" rx="3" fill="#86EFAC" opacity="0.4" />
      <rect x="290" y="120" width="20" height="12" rx="6" fill="#22C55E" opacity="0.5" />
      <rect x="240" y="95" width="50" height="60" rx="2" fill="white" opacity="0.45" stroke={accent} strokeWidth="1" />
      <text x="265" y="115" textAnchor="middle" fontSize="5" fill={secondary}>DIRECTORY</text>
      <motion.g animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 2, repeat: Infinity }}>
        <rect x="70" y="155" width="30" height="20" rx="2" fill={accent} opacity="0.4" />
      </motion.g>
    </g>
  );
}

function HostelScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="115" width="400" height="85" fill="#BBF7D0" opacity="0.25" />
      <motion.g animate={{ y: [0, -2, 0] }} transition={{ duration: 4, repeat: Infinity }}>
        <rect x="60" y="55" width="80" height="60" rx="3" fill={primary} opacity="0.35" />
        <polygon points="60,55 100,30 140,55" fill={secondary} opacity="0.4" />
        <rect x="72" y="68" width="12" height="12" fill={accent} opacity="0.5" />
        <rect x="92" y="68" width="12" height="12" fill={accent} opacity="0.5" />
        <rect x="112" y="68" width="12" height="12" fill={accent} opacity="0.5" />
        <rect x="72" y="88" width="12" height="12" fill={accent} opacity="0.5" />
        <rect x="92" y="88" width="12" height="12" fill={accent} opacity="0.5" />
      </motion.g>
      <rect x="220" y="120" width="100" height="40" rx="3" fill="white" opacity="0.5" stroke={primary} strokeWidth="1" />
      <text x="235" y="138" fontSize="6" fill={secondary} fontWeight="bold">HOSTEL REG</text>
      <rect x="235" y="143" width="70" height="3" fill={accent} opacity="0.5" />
      <circle cx="340" cy="140" r="8" fill="#FCD34D" opacity="0.5" />
      <rect x="337" y="140" width="6" height="12" rx="1" fill="#CA8A04" opacity="0.4" />
    </g>
  );
}

function WardenScene({ primary, secondary, accent }: EProps) {
  return (
    <g opacity="0.55">
      <rect x="0" y="100" width="400" height="100" fill="#E9D5FF" opacity="0.25" />
      <rect x="0" y="130" width="400" height="8" fill={secondary} opacity="0.2" />
      <rect x="30" y="70" width="25" height="60" fill={primary} opacity="0.25" />
      <rect x="65" y="70" width="25" height="60" fill={primary} opacity="0.25" />
      <rect x="100" y="70" width="25" height="60" fill={primary} opacity="0.25" />
      <rect x="200" y="55" width="90" height="50" rx="3" fill="white" opacity="0.55" stroke={secondary} strokeWidth="1" />
      <text x="215" y="72" fontSize="6" fill={secondary} fontWeight="bold">HOSTEL RULES</text>
      <line x1="210" y1="80" x2="280" y2="80" stroke={accent} strokeWidth="0.8" />
      <line x1="210" y1="88" x2="270" y2="88" stroke={accent} strokeWidth="0.8" />
      <rect x="310" y="115" width="50" height="35" rx="2" fill="#FEE2E2" opacity="0.5" stroke="#EF4444" strokeWidth="1" />
      <text x="335" y="135" textAnchor="middle" fontSize="5" fill="#DC2626">EMERGENCY</text>
      <motion.g animate={{ opacity: [0.4, 0.7, 0.4] }} transition={{ duration: 1.5, repeat: Infinity }}>
        <circle cx="335" cy="125" r="4" fill="#EF4444" opacity="0.6" />
      </motion.g>
    </g>
  );
}

const SCENE_MAP: Record<AgentType, ComponentType<EProps>> = {
  general: CampusScene,
  academic: ClassroomScene,
  faculty: FacultyOfficeScene,
  admission: AdmissionsScene,
  reception: ReceptionScene,
  hostel: HostelScene,
  warden: WardenScene,
};

export default function AgentEnvironmentArt({
  agent,
  primary,
  secondary,
  accent,
  className = "",
  compact = false,
}: {
  agent: AgentType;
  primary: string;
  secondary: string;
  accent: string;
  className?: string;
  compact?: boolean;
}) {
  const Scene = SCENE_MAP[agent];
  return (
    <svg
      viewBox={compact ? "0 0 400 120" : "0 0 400 200"}
      preserveAspectRatio="xMidYMax meet"
      className={`w-full h-full ${className}`}
      aria-hidden
    >
      <Scene primary={primary} secondary={secondary} accent={accent} />
    </svg>
  );
}
