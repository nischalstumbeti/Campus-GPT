import type { AgentType } from "@/hooks/useChat";

export type AgentTheme = {
  id: AgentType;
  label: string;
  roleTitle: string;
  tagline: string;
  description: string;
  envName: string;
  primary: string;
  secondary: string;
  accent: string;
  surface: string;
  bgFrom: string;
  bgVia: string;
  bgTo: string;
  bubble: string;
  bubbleUser: string;
  ring: string;
  glow: string;
  pattern: string;
};

export const AGENT_THEMES: Record<AgentType, AgentTheme> = {
  general: {
    id: "general",
    label: "Campus Guide",
    roleTitle: "University Assistant",
    tagline: "Your all-round Kalasalingam campus companion",
    description:
      "Navigate the university, find announcements, explore services, and get help with everyday campus questions.",
    envName: "Campus grounds",
    primary: "#1E40AF",
    secondary: "#1E3A8A",
    accent: "#60A5FA",
    surface: "#EFF6FF",
    bgFrom: "#F8FAFC",
    bgVia: "#EFF6FF",
    bgTo: "#DBEAFE",
    bubble: "bg-white/95 border-blue-100",
    bubbleUser: "bg-blue-700 text-white",
    ring: "ring-blue-400",
    glow: "rgba(30, 64, 175, 0.22)",
    pattern: "campus",
  },
  academic: {
    id: "academic",
    label: "Academic Advisor",
    roleTitle: "Academics",
    tagline: "Courses, timetable, marks & academic planning",
    description:
      "Guidance on subjects, curriculum, attendance, examinations, regulations, and your academic journey at KARE.",
    envName: "Modern classroom",
    primary: "#4338CA",
    secondary: "#3730A3",
    accent: "#818CF8",
    surface: "#EEF2FF",
    bgFrom: "#F5F3FF",
    bgVia: "#EEF2FF",
    bgTo: "#E0E7FF",
    bubble: "bg-white/95 border-indigo-100",
    bubbleUser: "bg-indigo-600 text-white",
    ring: "ring-indigo-400",
    glow: "rgba(67, 56, 202, 0.2)",
    pattern: "classroom",
  },
  faculty: {
    id: "faculty",
    label: "Faculty Desk",
    roleTitle: "Faculty Support",
    tagline: "Classes, office hours & department circulars",
    description:
      "Faculty cabin assistance for teaching schedules, department updates, meetings, and academic responsibilities.",
    envName: "Faculty cabin",
    primary: "#0F766E",
    secondary: "#115E59",
    accent: "#2DD4BF",
    surface: "#F0FDFA",
    bgFrom: "#F0FDFA",
    bgVia: "#CCFBF1",
    bgTo: "#99F6E4",
    bubble: "bg-white/95 border-teal-100",
    bubbleUser: "bg-teal-700 text-white",
    ring: "ring-teal-400",
    glow: "rgba(15, 118, 110, 0.2)",
    pattern: "faculty-office",
  },
  admission: {
    id: "admission",
    label: "Admission Counselor",
    roleTitle: "Admissions",
    tagline: "Applications, eligibility & enrollment",
    description:
      "Trusted help with programs, fees, deadlines, documents, eligibility, and the complete admission process.",
    envName: "Admissions desk",
    primary: "#C2410C",
    secondary: "#9A3412",
    accent: "#FB923C",
    surface: "#FFF7ED",
    bgFrom: "#FFFBEB",
    bgVia: "#FFEDD5",
    bgTo: "#FED7AA",
    bubble: "bg-white/95 border-orange-100",
    bubbleUser: "bg-orange-600 text-white",
    ring: "ring-orange-400",
    glow: "rgba(194, 65, 12, 0.2)",
    pattern: "admissions",
  },
  reception: {
    id: "reception",
    label: "Front Desk",
    roleTitle: "Reception",
    tagline: "Complete college information desk",
    description:
      "Full KARE information desk — campus facts, directions, contacts, admissions, fees, hostel, placements, facilities, and which office to visit.",
    envName: "University lobby",
    primary: "#0369A1",
    secondary: "#075985",
    accent: "#38BDF8",
    surface: "#F0F9FF",
    bgFrom: "#F0F9FF",
    bgVia: "#E0F2FE",
    bgTo: "#BAE6FD",
    bubble: "bg-white/95 border-sky-100",
    bubbleUser: "bg-sky-700 text-white",
    ring: "ring-sky-400",
    glow: "rgba(3, 105, 161, 0.2)",
    pattern: "reception",
  },
  hostel: {
    id: "hostel",
    label: "Hostel Manager",
    roleTitle: "Residential Services",
    tagline: "Hostel issues only",
    description:
      "Hostel-only desk for rooms, mess, hostel fees, facilities, rules, leave, and residential issues. Other topics belong at Reception.",
    envName: "Hostel admin office",
    primary: "#15803D",
    secondary: "#166534",
    accent: "#4ADE80",
    surface: "#F0FDF4",
    bgFrom: "#F0FDF4",
    bgVia: "#DCFCE7",
    bgTo: "#BBF7D0",
    bubble: "bg-white/95 border-green-100",
    bubbleUser: "bg-green-700 text-white",
    ring: "ring-green-400",
    glow: "rgba(21, 128, 61, 0.2)",
    pattern: "hostel",
  },
  warden: {
    id: "warden",
    label: "Hostel Warden",
    roleTitle: "Student Welfare",
    tagline: "Rules, leave, safety & hostel welfare",
    description:
      "Responsible support for hostel permissions, discipline, student welfare, complaints, and emergency assistance.",
    envName: "Hostel corridor",
    primary: "#6D28D9",
    secondary: "#5B21B6",
    accent: "#A78BFA",
    surface: "#F5F3FF",
    bgFrom: "#FAF5FF",
    bgVia: "#F3E8FF",
    bgTo: "#E9D5FF",
    bubble: "bg-white/95 border-violet-100",
    bubbleUser: "bg-violet-700 text-white",
    ring: "ring-violet-400",
    glow: "rgba(109, 40, 217, 0.2)",
    pattern: "warden",
  },
};

export const AGENT_LIST = Object.values(AGENT_THEMES);

export function getAgentTheme(agent: AgentType): AgentTheme {
  return AGENT_THEMES[agent] ?? AGENT_THEMES.general;
}
