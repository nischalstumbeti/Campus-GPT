"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import BrandLogo from "@/components/BrandLogo";
import { useBranding } from "@/components/ThemeProvider";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/campus", label: "Campus" },
  { href: "/timetable", label: "Timetable" },
  { href: "/attendance", label: "Attendance" },
  { href: "/marks", label: "Marks" },
  { href: "/faculty", label: "Faculty" },
  { href: "/planner", label: "Planner" },
];

export default function SiteHeader({ title }: { title?: string }) {
  const pathname = usePathname();
  const branding = useBranding();
  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-[#7C5AED]/10">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3 justify-between">
        <Link href="/" className="flex items-center gap-2">
          <BrandLogo size={36} />
          <div>
            <p className="font-bold text-primary leading-tight">{branding.app_name || "Campus-GPT"}</p>
            <p className="text-[11px] text-gray-500">{title || "Institute operations"}</p>
          </div>
        </Link>
        <nav className="flex flex-wrap items-center gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                pathname === l.href ? "bg-primary text-white" : "text-gray-600 hover:bg-primary/10 hover:text-primary"
              }`}
            >
              {l.label}
            </Link>
          ))}
          <Link href="/login" className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-primary border border-primary/30">
            Login
          </Link>
        </nav>
      </div>
    </header>
  );
}
