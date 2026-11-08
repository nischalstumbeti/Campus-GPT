"use client";

import type { ComponentType } from "react";
import { motion } from "framer-motion";
import type { AgentType } from "@/hooks/useChat";

type CProps = { primary: string; secondary: string; accent: string };

function BlinkEyes({ cx1, cy1, cx2, cy2 }: { cx1: number; cy1: number; cx2: number; cy2: number }) {
  return (
    <>
      <ellipse cx={cx1} cy={cy1} rx="2.8" ry="3.2" fill="#1F2937" className="agent-blink" />
      <ellipse cx={cx2} cy={cy2} rx="2.8" ry="3.2" fill="#1F2937" className="agent-blink" />
      <circle cx={cx1 - 0.8} cy={cy1 - 0.8} r="0.8" fill="white" opacity="0.7" />
      <circle cx={cx2 - 0.8} cy={cy2 - 0.8} r="0.8" fill="white" opacity="0.7" />
    </>
  );
}

export function GeneralCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}>
        <rect x="28" y="58" width="44" height="30" rx="10" fill={primary} />
        <path d="M36 58 L50 50 L64 58" fill="white" opacity="0.25" />
        <rect x="42" y="66" width="16" height="14" rx="2" fill="white" opacity="0.9" />
        <text x="50" y="76" textAnchor="middle" fontSize="6" fill={primary} fontWeight="bold">KARE</text>
        <circle cx="50" cy="36" r="18" fill="#F5C9A0" />
        <path d="M32 34 Q50 20 68 34 L66 40 Q50 28 34 40 Z" fill="#2C1810" />
        <BlinkEyes cx1={43} cy1={36} cx2={57} cy2={36} />
        <path d="M45 43 Q50 47 55 43" stroke="#B45309" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <motion.g animate={{ rotate: [-8, 8, -8] }} transition={{ duration: 2.5, repeat: Infinity }} style={{ transformOrigin: "72px 54px" }}>
          <rect x="66" y="48" width="10" height="14" rx="5" fill="#F5C9A0" />
          <path d="M70 48 L74 42 L78 48" fill={accent} />
        </motion.g>
        <path d="M38 28 L50 16 L62 28 L58 30 L50 22 L42 30 Z" fill={accent} />
        <rect x="44" y="14" width="12" height="5" rx="1" fill={secondary} />
        <circle cx="50" cy="19" r="2" fill="#FCD34D" />
      </motion.g>
    </g>
  );
}

export function AcademicCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3, repeat: Infinity }}>
        <path d="M26 58 Q50 52 74 58 L72 86 Q50 82 28 86 Z" fill={primary} />
        <rect x="30" y="58" width="40" height="28" rx="8" fill={primary} opacity="0.95" />
        <circle cx="50" cy="34" r="17" fill="#E8B88A" />
        <path d="M33 30 Q50 22 67 30" fill="#3D2314" />
        <BlinkEyes cx1={43} cy1={34} cx2={57} cy2={34} />
        <rect x="38" y="36" width="24" height="7" rx="3" fill="none" stroke="#374151" strokeWidth="1.5" />
        <line x1="41" y1="39" x2="59" y2="39" stroke="#6B7280" strokeWidth="0.8" />
        <motion.g animate={{ rotate: [-3, 3, -3] }} transition={{ duration: 2.2, repeat: Infinity }} style={{ transformOrigin: "18px 62px" }}>
          <rect x="10" y="54" width="14" height="18" rx="2" fill={accent} />
          <line x1="13" y1="58" x2="21" y2="58" stroke={secondary} strokeWidth="1" />
          <line x1="13" y1="62" x2="21" y2="62" stroke={secondary} strokeWidth="1" />
          <line x1="13" y1="66" x2="19" y2="66" stroke={secondary} strokeWidth="1" />
        </motion.g>
        <motion.g animate={{ y: [0, -2, 0] }} transition={{ duration: 2, repeat: Infinity }} style={{ transformOrigin: "76px 58px" }}>
          <rect x="68" y="50" width="16" height="12" rx="2" fill="#374151" />
          <rect x="70" y="52" width="12" height="7" rx="1" fill={accent} opacity="0.8" />
          <rect x="72" y="62" width="8" height="2" rx="1" fill="#9CA3AF" />
        </motion.g>
      </motion.g>
    </g>
  );
}

export function FacultyCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3.4, repeat: Infinity }}>
        <rect x="26" y="56" width="48" height="32" rx="9" fill={secondary} />
        <path d="M34 56 L50 48 L66 56" fill="white" opacity="0.2" />
        <rect x="46" y="62" width="8" height="18" fill="white" opacity="0.9" />
        <circle cx="50" cy="33" r="17" fill="#D4A574" />
        <path d="M33 28 Q50 18 67 28" fill="#4A3728" />
        <BlinkEyes cx1={43} cy1={33} cx2={57} cy2={33} />
        <path d="M45 40 Q50 43 55 40" stroke="#6B4423" strokeWidth="1.2" fill="none" />
        <motion.g animate={{ rotate: [0, 12, 0] }} transition={{ duration: 1.8, repeat: Infinity }} style={{ transformOrigin: "14px 64px" }}>
          <line x1="8" y1="64" x2="22" y2="50" stroke={accent} strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="8" cy="64" r="3" fill={accent} />
        </motion.g>
        <rect x="58" y="68" width="18" height="3" rx="1" fill="#D1D5DB" />
        <rect x="60" y="64" width="14" height="5" rx="1" fill="#9CA3AF" />
      </motion.g>
    </g>
  );
}

export function AdmissionCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 2.8, repeat: Infinity }}>
        <rect x="28" y="56" width="44" height="32" rx="9" fill={primary} />
        <circle cx="50" cy="34" r="17" fill="#F0C49A" />
        <path d="M34 30 Q50 22 66 30" fill="#2D1810" />
        <BlinkEyes cx1={43} cy1={34} cx2={57} cy2={34} />
        <path d="M46 41 Q50 44 54 41" stroke="#C2410C" strokeWidth="1.3" fill="none" strokeLinecap="round" />
        <motion.g animate={{ x: [0, 2, 0] }} transition={{ duration: 2, repeat: Infinity }}>
          <rect x="60" y="50" width="18" height="24" rx="3" fill="white" stroke={accent} strokeWidth="2" />
          <text x="69" y="60" textAnchor="middle" fontSize="5" fill={primary} fontWeight="bold">ADM</text>
          <line x1="63" y1="64" x2="75" y2="64" stroke={secondary} strokeWidth="1" />
          <line x1="63" y1="68" x2="73" y2="68" stroke={secondary} strokeWidth="1" />
          <path d="M65 72 L69 76 L75 70" stroke={accent} strokeWidth="1.5" fill="none" />
        </motion.g>
        <rect x="14" y="62" width="14" height="18" rx="2" fill={accent} opacity="0.85" />
        <text x="21" y="73" textAnchor="middle" fontSize="5" fill="white" fontWeight="bold">KLU</text>
      </motion.g>
    </g>
  );
}

export function ReceptionCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3.1, repeat: Infinity }}>
        <rect x="28" y="56" width="44" height="32" rx="9" fill={primary} />
        <circle cx="50" cy="34" r="17" fill="#F5D0B0" />
        <path d="M34 28 Q50 20 66 28" fill="#1F1210" />
        <BlinkEyes cx1={43} cy1={34} cx2={57} cy2={34} />
        <path d="M45 41 Q50 45 55 41" stroke="#BE185D" strokeWidth="1.3" fill="none" />
        <path d="M36 30 Q30 26 28 34" stroke={accent} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        <ellipse cx="28" cy="34" rx="4" ry="5" fill={accent} />
        <motion.g animate={{ scale: [1, 1.06, 1] }} transition={{ duration: 1.5, repeat: Infinity }}>
          <rect x="12" y="64" width="24" height="12" rx="4" fill={accent} />
          <text x="24" y="72" textAnchor="middle" fontSize="6" fill="white" fontWeight="bold">Welcome</text>
        </motion.g>
      </motion.g>
    </g>
  );
}

export function HostelCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3.2, repeat: Infinity }}>
        <rect x="28" y="56" width="44" height="32" rx="9" fill={primary} />
        <rect x="38" y="64" width="24" height="4" rx="1" fill={accent} />
        <circle cx="50" cy="34" r="17" fill="#E8BE96" />
        <rect x="38" y="24" width="24" height="8" rx="4" fill="#4A3728" />
        <BlinkEyes cx1={43} cy1={34} cx2={57} cy2={34} />
        <motion.g animate={{ rotate: [-6, 6, -6] }} transition={{ duration: 2.3, repeat: Infinity }} style={{ transformOrigin: "70px 58px" }}>
          <circle cx="70" cy="54" r="6" fill={accent} />
          <rect x="66" y="54" width="8" height="10" rx="2" fill="#FCD34D" />
          <circle cx="70" cy="58" r="2" fill={secondary} />
        </motion.g>
        <rect x="12" y="58" width="16" height="20" rx="2" fill="white" opacity="0.9" stroke={accent} strokeWidth="1" />
        <line x1="15" y1="63" x2="25" y2="63" stroke={primary} strokeWidth="0.8" />
        <line x1="15" y1="68" x2="25" y2="68" stroke={primary} strokeWidth="0.8" />
      </motion.g>
    </g>
  );
}

export function WardenCharacter({ primary, secondary, accent }: CProps) {
  return (
    <g>
      <ellipse cx="50" cy="92" rx="30" ry="5" fill="rgba(0,0,0,0.1)" />
      <motion.g className="agent-breathe" animate={{ y: [0, -3, 0] }} transition={{ duration: 3.3, repeat: Infinity }}>
        <rect x="26" y="56" width="48" height="32" rx="9" fill={secondary} />
        <circle cx="50" cy="33" r="17" fill="#DDB892" />
        <path d="M33 26 Q50 18 67 26" fill="#1F2937" />
        <BlinkEyes cx1={43} cy1={33} cx2={57} cy2={33} />
        <path d="M46 40 L50 43 L54 40" stroke="#374151" strokeWidth="1.3" fill="none" />
        <motion.g animate={{ scale: [1, 1.05, 1] }} transition={{ duration: 2.5, repeat: Infinity }} style={{ transformOrigin: "50px 64px" }}>
          <path d="M42 60 L50 50 L58 60 L55 72 L45 72 Z" fill={accent} stroke="white" strokeWidth="1.5" />
          <text x="50" y="66" textAnchor="middle" fontSize="5" fill="white" fontWeight="bold">W</text>
        </motion.g>
        <rect x="62" y="52" width="14" height="18" rx="2" fill="#FEE2E2" stroke="#EF4444" strokeWidth="1" />
        <text x="69" y="63" textAnchor="middle" fontSize="4" fill="#DC2626" fontWeight="bold">SOS</text>
      </motion.g>
    </g>
  );
}

export const CHARACTER_MAP: Record<AgentType, ComponentType<CProps>> = {
  general: GeneralCharacter,
  academic: AcademicCharacter,
  faculty: FacultyCharacter,
  admission: AdmissionCharacter,
  reception: ReceptionCharacter,
  hostel: HostelCharacter,
  warden: WardenCharacter,
};
