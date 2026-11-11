"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { apiFetch, clearToken } from "@/lib/api";
import NotificationBell from "@/components/NotificationBell";
import AdminMarquee from "@/components/AdminMarquee";
import { useBranding, useBrandingReady } from "@/components/ThemeProvider";
import { sanitizeNoticeHtml } from "@/lib/noticeHtml";

type Me = {
  full_name: string;
  role: string;
  username: string;
  demo_banner?: string;
};

type NavItem = { href: string; label: string; badge?: string; icon: IconName };
type NavGroup = { label: string; children: NavItem[] };
type NavEntry = NavItem | NavGroup;

const STUDENT_MENU: NavEntry[] = [
  { href: "/student", label: "Dashboard", icon: "home" },
  {
    label: "Semester",
    children: [
      { href: "/student/section/attendance", label: "Attendance Details", icon: "check" },
      { href: "/student/section/marks", label: "Marks Details", icon: "chart" },
      { href: "/student/section/registration", label: "Registration", icon: "clipboard" },
    ],
  },
  {
    label: "Examinations",
    children: [
      { href: "/student/exams", label: "Answer Script", icon: "file" },
      { href: "/student/section/revaluation", label: "Revaluation", icon: "refresh" },
      { href: "/student/section/arrear", label: "Arrear", icon: "alert" },
      { href: "/student/section/backlog", label: "Backlog", icon: "layers" },
    ],
  },
  { href: "/student/section/hall-ticket", label: "Hall Ticket", icon: "ticket" },
  { href: "/student/section/course-registration", label: "Course Registration", icon: "book" },
  { href: "/student/section/course-withdrawal", label: "Course Withdrawal", icon: "undo" },
  { href: "/student/academics", label: "Grade", icon: "award" },
  { href: "/student/timetable", label: "Seating & Time Table", icon: "calendar" },
  { href: "/student/section/internships", label: "Internships", icon: "link" },
  { href: "/student/section/non-cgpa", label: "Non CGPA", icon: "layers" },
  { href: "/student/section/makeup", label: "Make-up", icon: "plus" },
  {
    label: "Fees",
    children: [
      { href: "/student/fees", label: "Pay fees", icon: "wallet" },
      { href: "/student/section/fee-status", label: "Fee status", icon: "receipt" },
    ],
  },
  { href: "/student/section/feedback", label: "Course Feedback", icon: "message" },
  { href: "/student/announcements", label: "Circulars", icon: "megaphone" },
  { href: "/messages", label: "Messages", icon: "chat" },
  { href: "/ack", label: "Acknowledgements", icon: "file" },
  { href: "/directory", label: "Directory", icon: "users" },
  { href: "/student/hostel", label: "Hostel", icon: "building" },
  { href: "/student/complaints", label: "Complaints", icon: "alert" },
  { href: "/settings", label: "Change password", icon: "lock" },
];

function isGroup(entry: NavEntry): entry is NavGroup {
  return "children" in entry;
}

type IconName =
  | "home" | "check" | "chart" | "clipboard" | "file" | "refresh" | "alert" | "layers"
  | "ticket" | "book" | "cap" | "undo" | "award" | "calendar" | "briefcase" | "globe"
  | "star" | "link" | "plus" | "wallet" | "receipt" | "message" | "megaphone" | "chat"
  | "building" | "lock" | "users" | "folder" | "activity";

function NavIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, string> = {
    home: "M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z",
    check: "M5 12.5 9.2 17 19 7",
    chart: "M5 19V9M12 19V5M19 19v-7",
    clipboard: "M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1ZM7 6h10v14H7V6Z",
    file: "M7 3h7l5 5v13H7V3Zm7 0v5h5",
    refresh: "M19 12a7 7 0 1 1-2-4.9M19 4v5h-5",
    alert: "M12 4 3 19h18L12 4Zm0 6v4M12 16.5h.01",
    layers: "M12 4 3 9l9 5 9-5-9-5Zm-9 8 9 5 9-5",
    ticket: "M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4V8Z",
    book: "M5 5.5A2.5 2.5 0 0 1 7.5 3H20v16H7.5A2.5 2.5 0 0 0 5 21.5V5.5Z",
    cap: "M3 10 12 5l9 5-9 5-9-5Zm4 3.2V16c0 1.5 2.2 3 5 3s5-1.5 5-3v-2.8",
    undo: "M8 8H4v4M4.5 12A8 8 0 1 0 6 7",
    award: "M12 3 9 9H3l5 4-2 7 6-4 6 4-2-7 5-4h-6L12 3Z",
    calendar: "M5 6h14v14H5V6Zm0 4h14M8 3v4M16 3v4",
    briefcase: "M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M4 7h16v12H4V7Zm0 5h16",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18",
    star: "M12 3.5 14.2 9H20l-4.6 3.5L17.2 18 12 14.8 6.8 18l1.8-5.5L4 9h5.8L12 3.5Z",
    link: "M10 13a4 4 0 0 0 6 0l2-2a4 4 0 0 0-6-6l-1 1M14 11a4 4 0 0 0-6 0l-2 2a4 4 0 0 0 6 6l1-1",
    plus: "M12 5v14M5 12h14",
    wallet: "M4 7h16v12H4V7Zm12 6h4M4 7l2-3h10l2 3",
    receipt: "M7 3h10v18l-2-1.5L13 21l-2-1.5L9 21l-2-1.5L5 21V5a2 2 0 0 1 2-2Zm2 6h6M9 13h6",
    message: "M5 6h14v9H8l-3 3V6Z",
    megaphone: "M5 10v4h3l7 4V6L8 10H5Zm12 2h2",
    chat: "M5 6h14v10H8l-3 3V6Z",
    building: "M5 20V6l7-3 7 3v14H5Zm4-4h2M13 16h2M9 12h2M13 12h2",
    lock: "M8 11V8a4 4 0 1 1 8 0v3M6 11h12v9H6v-9Z",
    users: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 1a2.5 2.5 0 1 0 0-5M4 19a5 5 0 0 1 10 0M15 19a4 4 0 0 1 4-4",
    folder: "M3 7h6l2 2h10v10H3V7Z",
    activity: "M3 12h4l3-8 4 16 3-8h4",
  };
  return (
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d={paths[name]} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function itemClass(active: boolean) {
  return `flex items-center gap-2.5 min-h-11 px-3 py-2 rounded-md text-[15px] leading-5 ${
    active
      ? "bg-white text-brand font-semibold shadow-[inset_3px_0_0_var(--brand)]"
      : "text-slate-800 hover:bg-white"
  }`;
}

function NavItemLink({ item, active, onNavigate }: { item: NavItem; active: boolean; onNavigate?: () => void }) {
  return (
    <Link href={item.href} onClick={onNavigate} className={itemClass(active)}>
      <span className={active ? "text-brand" : "text-slate-500"}>
        <NavIcon name={item.icon} />
      </span>
      <span className="flex-1">{item.label}</span>
      {item.badge ? (
        <span className="rounded bg-rose-500 px-1 py-0.5 text-[9px] font-bold uppercase leading-none text-white">{item.badge}</span>
      ) : null}
    </Link>
  );
}

const GROUP_ICONS: Record<string, IconName> = {
  Semester: "calendar",
  Examinations: "file",
  Fees: "wallet",
};

function StudentNav({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  return (
    <>
      {STUDENT_MENU.map((entry) => {
        if (!isGroup(entry)) {
          return (
            <NavItemLink
              key={entry.href + entry.label}
              item={entry}
              active={pathname === entry.href}
              onNavigate={onNavigate}
            />
          );
        }
        const childActive = entry.children.some((child) => pathname === child.href);
        const expanded = open[entry.label] ?? (entry.label === "Semester" || childActive);
        return (
          <div key={entry.label}>
            <button
              type="button"
              className={`flex w-full items-center gap-2.5 min-h-11 px-3 py-2 rounded-md text-[15px] leading-5 hover:bg-white ${childActive ? "text-brand font-semibold" : "text-slate-800"}`}
              onClick={() => setOpen((current) => ({ ...current, [entry.label]: !expanded }))}
              aria-expanded={expanded}
            >
              <span className={childActive ? "text-brand" : "text-slate-500"}>
                <NavIcon name={GROUP_ICONS[entry.label] || "folder"} />
              </span>
              <span className="flex-1 text-left font-medium">{entry.label}</span>
              <svg viewBox="0 0 24 24" className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? "rotate-90" : ""}`} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {expanded ? (
              <div className="mt-1 ml-5 space-y-1 border-l border-slate-200 pl-2">
                {entry.children.map((child) => (
                  <NavItemLink
                    key={child.href + child.label}
                    item={child}
                    active={pathname === child.href}
                    onNavigate={onNavigate}
                  />
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
    </>
  );
}

type FacultyLink = { href: string; label: string; icon: IconName };
type FacultyNode = FacultyLink | { label: string; icon: IconName; children: FacultyLink[] };

const FACULTY_SECTIONS: { title: string; items: FacultyNode[] }[] = [
  {
    title: "Manage",
    items: [
      { href: "/faculty/module/exam-pattern", label: "Exam Pattern", icon: "file" },
      {
        label: "Attendance",
        icon: "check",
        children: [
          { href: "/faculty/attendance", label: "Enter attendance", icon: "check" },
          { href: "/faculty/classes", label: "Class list", icon: "users" },
        ],
      },
      {
        label: "Marks",
        icon: "chart",
        children: [
          { href: "/faculty/marks", label: "Enter marks", icon: "chart" },
          { href: "/faculty/students", label: "Student profiles", icon: "users" },
        ],
      },
      { href: "/faculty/timetable", label: "My Class Time Table", icon: "calendar" },
      { href: "/faculty/module/biometric", label: "Attendance", icon: "check" },
      {
        label: "Assign Courses",
        icon: "book",
        children: [{ href: "/faculty/classes", label: "My classes", icon: "book" }],
      },
      {
        label: "Mark Approval",
        icon: "clipboard",
        children: [{ href: "/faculty/marks", label: "Review marks", icon: "chart" }],
      },
      {
        label: "Grade Entry",
        icon: "award",
        children: [{ href: "/faculty/students", label: "Student grades", icon: "award" }],
      },
    ],
  },
  {
    title: "Other permission",
    items: [
      {
        label: "My Mentoring Wards",
        icon: "users",
        children: [
          { href: "/faculty/students", label: "Mentees", icon: "users" },
          { href: "/faculty/leaves", label: "Student leave", icon: "calendar" },
          { href: "/faculty/complaints", label: "Complaints", icon: "alert" },
          { href: "/faculty/fees", label: "Fee deadlines", icon: "wallet" },
          { href: "/faculty/approvals", label: "Approvals", icon: "clipboard" },
        ],
      },
      { href: "/faculty/module/question-bank", label: "Question Bank", icon: "book" },
      { href: "/directory", label: "Directory", icon: "users" },
      { href: "/messages", label: "Messages", icon: "chat" },
      { href: "/settings", label: "Change password", icon: "lock" },
    ],
  },
];

function isFacultyNodeGroup(item: FacultyNode): item is { label: string; icon: IconName; children: FacultyLink[] } {
  return "children" in item;
}

function FacultyNav({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const item = "flex w-full items-center gap-3 min-h-11 px-3 rounded-md text-[15px] text-slate-200 hover:bg-white/10";
  return (
    <div className="space-y-4">
      <Link
        href="/faculty"
        onClick={onNavigate}
        className={`flex min-h-12 items-center gap-3 rounded-md px-4 text-[15px] font-semibold text-white ${
          pathname === "/faculty" ? "bg-[#e23d2b]" : "bg-[#e23d2b]/90 hover:bg-[#e23d2b]"
        }`}
      >
        <span className="text-amber-300">
          <NavIcon name="award" />
        </span>
        Dashboard
      </Link>
      {FACULTY_SECTIONS.map((section) => (
        <div key={section.title}>
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{section.title}</p>
          <div className="space-y-0.5">
            {section.items.map((entry) => {
              if (!isFacultyNodeGroup(entry)) {
                const active = pathname === entry.href;
                return (
                  <Link key={entry.href} href={entry.href} onClick={onNavigate} className={`${item} ${active ? "bg-white/10 text-white" : ""}`}>
                    <span className="text-slate-300"><NavIcon name={entry.icon} /></span>
                    <span className="flex-1">{entry.label}</span>
                  </Link>
                );
              }
              const childActive = entry.children.some((child) => pathname === child.href);
              const expanded = open[entry.label] ?? childActive;
              return (
                <div key={entry.label}>
                  <button
                    type="button"
                    className={`${item} ${childActive ? "text-white" : ""}`}
                    aria-expanded={expanded}
                    onClick={() => setOpen((current) => ({ ...current, [entry.label]: !expanded }))}
                  >
                    <span className="text-slate-300"><NavIcon name={entry.icon} /></span>
                    <span className="flex-1 text-left">{entry.label}</span>
                    <svg viewBox="0 0 24 24" className={`h-4 w-4 text-slate-400 transition-transform ${expanded ? "rotate-90" : ""}`} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {expanded ? (
                    <div className="ml-5 mt-0.5 space-y-0.5 border-l border-white/10 pl-2">
                      {entry.children.map((child) => (
                        <Link
                          key={entry.label + child.href + child.label}
                          href={child.href}
                          onClick={onNavigate}
                          className={`${item} ${pathname === child.href ? "bg-white/10 text-white" : ""}`}
                        >
                          <span className="flex-1">{child.label}</span>
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

const HOSTEL: NavItem[] = [
  { href: "/hostel", label: "Dashboard", icon: "home" },
  { href: "/hostel/attendance", label: "Inmate attendance", icon: "check" },
  { href: "/hostel/leaves", label: "Leave Approvals", icon: "calendar" },
  { href: "/hostel/rooms", label: "Room Allocations", icon: "building" },
  { href: "/directory", label: "Directory", icon: "users" },
  { href: "/messages", label: "Messages", icon: "chat" },
  { href: "/hostel/complaints", label: "Hostel Complaints", icon: "alert" },
  { href: "/hostel/fees", label: "Fee deadlines", icon: "wallet" },
  { href: "/settings", label: "Change password", icon: "lock" },
];

const ADMIN: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: "home" },
  { href: "/admin/connections", label: "Connections", icon: "activity" },
  { href: "/admin/cms", label: "Admin CMS", icon: "folder" },
  { href: "/admin/fees", label: "Fee deadlines", icon: "wallet" },
  { href: "/admin/allocation", label: "Course allocation", icon: "clipboard" },
  { href: "/admin/records", label: "Timetable & exams", icon: "calendar" },
  { href: "/admin/marks", label: "Enter marks", icon: "chart" },
  { href: "/admin/attendance", label: "Enter attendance", icon: "check" },
  { href: "/admin/applications", label: "Exam applications", icon: "clipboard" },
  { href: "/admin/hall-ticket", label: "Hall ticket", icon: "ticket" },
  { href: "/directory", label: "Directory", icon: "users" },
  { href: "/messages", label: "Inbox", icon: "chat" },
  { href: "/admin/users", label: "Users", icon: "users" },
  { href: "/admin/students/view", label: "View students", icon: "users" },
  { href: "/admin/students", label: "Filter / edit students", icon: "clipboard" },
  { href: "/admin/services", label: "Service monitor", icon: "activity" },
  { href: "/ack", label: "Acknowledgements", icon: "file" },
  { href: "/admin/audit", label: "Audit Logs", icon: "file" },
  { href: "/settings", label: "Change password", icon: "lock" },
];

function linksForRole(role?: string) {
  if (!role) return [];
  if (role === "student") return [];
  if (role === "faculty" || role === "hod" || role === "school_dean") return [];
  if (role === "hostel_admin" || role === "warden" || role === "hostel_warden") return HOSTEL;
  if (
    ["admin", "university_admin", "super_admin", "department_admin", "exam_admin", "director", "coe", "operator", "developer"].includes(
      role
    )
  ) {
    return ADMIN;
  }
  return [];
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const branding = useBranding();
  const brandReady = useBrandingReady();
  const shellTitle = branding.header_title || branding.app_name;
  const [me, setMe] = useState<Me | null>(null);
  const [authError, setAuthError] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [adminReturn, setAdminReturn] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 12000);
    setAdminReturn(!!localStorage.getItem("uis_admin_return"));
    apiFetch<Me>("/api/v1/auth/me")
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch((err) => {
        if (cancelled) return;
        // Only hard-logout on definite auth failures
        const msg = String(err?.message || err || "");
        if (msg.includes("401") || msg.includes("Not authenticated") || msg.includes("Invalid")) {
          clearToken();
          router.replace("/login");
          return;
        }
        setAuthError(true);
      })
      .finally(() => clearTimeout(t));
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [router]);

  const links = linksForRole(me?.role);
  const facultyShell = me?.role === "faculty" || me?.role === "hod" || me?.role === "school_dean";

  const logout = () => {
    clearToken();
    localStorage.removeItem("uis_admin_return");
    router.replace("/login");
  };

  const returnToAdmin = () => {
    const token = localStorage.getItem("uis_admin_return");
    if (token) localStorage.setItem("uis_token", token);
    localStorage.removeItem("uis_admin_return");
    window.location.href = "/admin/users";
  };

  const NavLinks = ({ onNavigate }: { onNavigate?: () => void }) => (
    <>
      {me?.role === "student" ? <StudentNav pathname={pathname} onNavigate={onNavigate} /> : null}
      {(me?.role === "faculty" || me?.role === "hod" || me?.role === "school_dean") ? <FacultyNav pathname={pathname} onNavigate={onNavigate} /> : null}
      {links.map((l) => {
        const isRoot = ["/faculty", "/student", "/hostel", "/admin"].includes(l.href);
        const active = pathname === l.href || (!isRoot && pathname.startsWith(l.href + "/"));
        return (
          <Link
            key={l.href}
            href={l.href}
            onClick={onNavigate}
            className={itemClass(active)}
            {...(l.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            <span className={active ? "text-brand" : "text-slate-500"}>
              <NavIcon name={l.icon} />
            </span>
            <span className="flex-1">{l.label}</span>
          </Link>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen flex bg-transparent">
      <aside className={`hidden md:flex md:sticky md:top-0 md:h-screen w-72 shrink-0 flex-col overflow-hidden border-r ${facultyShell ? "bg-[#1b2036] text-slate-200 border-[#121628]" : "bg-panel text-slate-800 border-slate-200"}`}>
        <div className={`px-4 py-4 border-b flex items-center gap-3 ${facultyShell ? "border-white/10" : "border-slate-200 bg-white"}`}>
          {!brandReady ? (
            <span className="h-10 w-10 rounded-md bg-slate-200 animate-pulse" aria-hidden />
          ) : branding.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-10 w-10 object-contain bg-white rounded-md p-0.5" />
          ) : null}
          <div className="min-w-0">
            {!brandReady ? (
              <span className="block h-4 w-24 rounded bg-slate-200 animate-pulse" aria-hidden />
            ) : (
              <p className={`text-[15px] font-bold leading-tight ${facultyShell ? "text-white" : "text-brand"}`}>{branding.app_name || shellTitle}</p>
            )}
            {brandReady && branding.header_subtitle ? (
              <p className={`text-xs leading-snug mt-1 ${facultyShell ? "text-slate-400" : "text-slate-500"}`}>{branding.header_subtitle}</p>
            ) : null}
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {!me && !authError && <p className="px-3 py-2 text-sm text-slate-400">Loading menu…</p>}
          {authError && <p className="px-3 py-2 text-sm text-amber-700">Could not load profile. Retry or sign in again.</p>}
          <NavLinks />
        </nav>
        <div className={`p-3 border-t ${facultyShell ? "border-white/10 bg-[#15192c]" : "border-slate-200 bg-white"}`}>
          <p className={`truncate text-sm font-semibold ${facultyShell ? "text-white" : "text-slate-900"}`}>{me?.full_name || "…"}</p>
          <p className={`text-xs capitalize ${facultyShell ? "text-slate-400" : "text-slate-500"}`}>{me?.role?.replaceAll("_", " ") || ""}</p>
          <a
            href={process.env.NEXT_PUBLIC_CAMPUS_GPT_URL || "http://localhost:3001"}
            target="_blank"
            rel="noreferrer"
            className={`mt-3 flex min-h-10 items-center justify-center rounded-md border px-3 text-sm font-medium ${facultyShell ? "border-white/15 text-white hover:bg-white/10" : "border-slate-200 text-brand hover:bg-slate-50"}`}
          >
            Open Campus-GPT
          </a>
          <button onClick={logout} className={`mt-2 flex min-h-10 w-full items-center justify-center rounded-md px-3 text-sm font-medium text-white hover:opacity-90 ${facultyShell ? "bg-[#e23d2b]" : "bg-brand"}`}>
            Logout
          </button>
        </div>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              className="md:hidden rounded-md border border-slate-200 px-2 py-1 text-sm text-brand"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              aria-label="Open navigation menu"
            >
              Menu
            </button>
            {!brandReady ? (
              <span className="md:hidden h-9 w-9 rounded bg-slate-200 animate-pulse" aria-hidden />
            ) : branding.logo_url ? (
              <img src={branding.logo_url} alt="" className="md:hidden h-9 w-9 object-contain" />
            ) : null}
            <div className="min-w-0">
              {!brandReady ? (
                <span className="block h-4 w-48 rounded bg-slate-200 animate-pulse" aria-hidden />
              ) : (
                <p className="text-sm font-semibold text-brand truncate">{shellTitle}</p>
              )}
              {brandReady && branding.header_subtitle ? (
                <p className="text-[11px] text-slate-500">{branding.header_subtitle}</p>
              ) : null}
            </div>
          </div>
          <NotificationBell />
        </header>
        {adminReturn ? (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex flex-wrap items-center justify-between gap-2 text-sm text-amber-950">
            <span>You are signed in as {me?.full_name || "this user"} from an admin account.</span>
            <button type="button" onClick={returnToAdmin} className="rounded-md bg-amber-900 px-3 py-1 text-white text-xs font-semibold">
              Return to admin
            </button>
          </div>
        ) : null}
        {menuOpen && (
          <div className={`md:hidden border-b ${facultyShell ? "bg-[#1b2036] text-slate-200 border-[#121628]" : "bg-panel text-slate-700 border-slate-200"}`}>
            <nav className="p-3 space-y-1 max-h-[70vh] overflow-y-auto">
              <NavLinks onNavigate={() => setMenuOpen(false)} />
              <button
                type="button"
                onClick={logout}
                className="mt-2 flex min-h-11 w-full items-center rounded-md px-3 text-[15px] font-medium text-brand"
              >
                Logout
              </button>
            </nav>
          </div>
        )}
        <AdminMarquee />
        <main className="flex-1 p-4 md:p-6 overflow-auto">{children}</main>
        {brandReady && branding.footer_text ? (
          <footer
            className="px-4 py-3 text-center text-[11px] text-slate-500 border-t bg-white/80 [&_a]:underline [&_a]:text-brand"
            dangerouslySetInnerHTML={{ __html: sanitizeNoticeHtml(branding.footer_text) }}
          />
        ) : null}
      </div>
    </div>
  );
}
