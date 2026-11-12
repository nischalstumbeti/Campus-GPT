"use client";

import Link from "next/link";
import BrandLogo from "@/components/BrandLogo";
import { useBranding } from "@/components/ThemeProvider";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import NotificationBell from "@/components/NotificationBell";
import AdminMarquee from "@/components/AdminMarquee";

type Item = { href: string; label: string };

const UIS_URL = process.env.NEXT_PUBLIC_UIS_URL || "http://localhost:3000";

const STUDENT_BASE: Item[] = [
  { href: "/chat", label: "Chat" },
  { href: "/academics", label: "My Academic Life" },
  { href: "/timetable", label: "Timetable" },
  { href: "/fees", label: "Pay fees" },
  { href: "/messages", label: "Messages" },
  { href: "/university", label: "University" },
  { href: "/calendar", label: "Planner" },
  { href: "/documents", label: "Documents" },
  { href: "/career", label: "Career" },
  { href: "/achievements", label: "Achievements" },
  { href: "/privacy", label: "Consent" },
  { href: "/settings", label: "Settings" },
];

function studentNav(isHosteller?: boolean): Item[] {
  if (!isHosteller) return STUDENT_BASE;
  // Insert Hostel leave after Documents for hostellers only
  const docsIdx = STUDENT_BASE.findIndex((i) => i.href === "/documents");
  const items = [...STUDENT_BASE];
  items.splice(docsIdx + 1, 0, { href: "/leave", label: "Hostel" });
  return items;
}

const FACULTY: Item[] = [
  { href: "/chat", label: "Chat" },
  { href: "/faculty", label: "Availability" },
  { href: "/messages", label: "Messages" },
  { href: "/faculty/fees", label: "Fee deadlines" },
  { href: "/drafts", label: "Recurring drafts" },
  { href: "/calendar", label: "Planner" },
  { href: "/university", label: "Notices" },
  { href: "/privacy", label: "Privacy" },
  { href: "/settings", label: "Settings" },
];

const ADMIN: Item[] = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/insight", label: "Thinking" },
  { href: "/admin/connections", label: "Connections" },
  { href: "/admin/cms", label: "CMS" },
  { href: "/admin/observability", label: "Observability" },
  { href: "/admin/audit", label: "Audit trail" },
  { href: "/admin/upload", label: "Knowledge" },
  { href: "/admin/announcements", label: "Announcements" },
  { href: "/admin/fees", label: "Fee deadlines" },
  { href: "/messages", label: "Inbox" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/evaluation", label: "Evaluation" },
  { href: "/university", label: "View notices" },
  { href: "/privacy", label: "Permissions" },
  { href: "/settings", label: "Settings" },
];

const HOSTEL: Item[] = [
  { href: "/chat", label: "Chat" },
  { href: "/messages", label: "Hostel inbox" },
  { href: "/hostel", label: "Leave queue" },
  { href: "/university", label: "Notices" },
  { href: "/privacy", label: "Privacy" },
  { href: "/settings", label: "Settings" },
];

function NavLinks({
  links,
  pathname,
  onNavigate,
}: {
  links: Item[];
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <>
      {links.map((l) => {
        const isRoot = l.href === "/admin";
        const active = pathname === l.href || (!isRoot && pathname.startsWith(l.href + "/"));
        return (
          <Link
            key={l.href}
            href={l.href}
            onClick={onNavigate}
            className={`block px-3 py-2 rounded-lg text-sm font-medium ${
              active ? "bg-primary text-white" : "text-gray-600 hover:bg-primary/10 hover:text-primary"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </>
  );
}

export default function CopilotShell({
  children,
  title,
  fill,
}: {
  children: React.ReactNode;
  title?: string;
  fill?: boolean;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const branding = useBranding();
  const role = user?.role || "student";
  const links =
    role === "admin" || role === "super_admin"
      ? ADMIN
      : role === "faculty"
        ? FACULTY
        : role === "hostel_admin" || role === "hostel_warden"
          ? HOSTEL
          : studentNav(!!user?.is_hosteller || user?.residence_type === "hostel");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <div className={fill ? "h-[100dvh] flex overflow-hidden bg-[#FAFAFE]" : "min-h-screen flex bg-[#FAFAFE]"}>
      <aside className="hidden md:flex w-56 shrink-0 flex-col border-r border-[#7C5AED]/10 bg-white">
        <Link href="/workspace" className="flex items-center gap-2 px-4 py-4 border-b border-gray-100">
          <BrandLogo size={32} />
          <div>
            <p className="font-bold text-sm text-primary leading-tight">{branding.app_name || "Campus-GPT"}</p>
            <p className="text-[10px] text-gray-500">{branding.tagline || "KARE AI companion"}</p>
          </div>
        </Link>
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5" aria-label="Main">
          <NavLinks links={links} pathname={pathname} />
        </nav>
        <div className="p-3 border-t border-gray-100">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="min-w-0">
              <p className="text-xs text-gray-500 truncate">{user?.full_name}</p>
              <p className="text-[10px] text-gray-400 capitalize">{role}</p>
            </div>
            <NotificationBell />
          </div>
          <a
            href={UIS_URL}
            target="_blank"
            rel="noreferrer"
            className="block text-xs text-primary hover:underline mb-2"
          >
            Open KARE UIS
          </a>
          <button onClick={logout} className="text-xs text-red-600 hover:underline">
            Logout
          </button>
        </div>
      </aside>
      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        <header className="md:hidden flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-white">
          <button
            type="button"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen((o) => !o)}
            className="text-sm font-bold text-primary"
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
          <p className="font-bold text-primary text-sm">{title || "Campus-GPT"}</p>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <button onClick={logout} className="text-xs text-red-600">
              Logout
            </button>
          </div>
        </header>
        {menuOpen && (
          <nav
            id="mobile-nav"
            className="md:hidden border-b border-gray-100 bg-white p-2 space-y-0.5 max-h-[50vh] overflow-y-auto"
            aria-label="Mobile"
          >
            <NavLinks links={links} pathname={pathname} onNavigate={() => setMenuOpen(false)} />
            <a href={UIS_URL} target="_blank" rel="noreferrer" className="block px-3 py-2 text-sm text-primary">
              Open KARE UIS
            </a>
          </nav>
        )}
        <AdminMarquee />
        <div className={`flex-1 min-h-0 ${fill ? "overflow-hidden" : "overflow-auto"}`}>{children}</div>
        <nav className="md:hidden flex overflow-x-auto gap-1 px-2 py-2 border-t border-gray-100 bg-white" aria-label="Quick">
          {links.slice(0, 5).map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`shrink-0 px-2 py-1 rounded-lg text-[11px] ${pathname === l.href ? "bg-primary text-white" : "text-gray-600"}`}
            >
              {l.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            className="shrink-0 px-2 py-1 rounded-lg text-[11px] text-primary font-medium"
          >
            More
          </button>
        </nav>
      </div>
    </div>
  );
}
