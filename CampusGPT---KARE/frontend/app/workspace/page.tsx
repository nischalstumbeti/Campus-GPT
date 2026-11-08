"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  MessageCircle,
  ListTodo,
  CalendarDays,
  Home,
  ClipboardCheck,
  GraduationCap,
  TrendingUp,
  CalendarRange,
} from "lucide-react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { useAuth } from "@/hooks/useAuth";
import { apiGet } from "@/lib/api";

const STUDENT_TOOLS = [
  { href: "/chat", icon: MessageCircle, title: "AI academic assistant", desc: "Ask about classes, marks, attendance, and faculty hours." },
  { href: "/tasks", icon: ListTodo, title: "Task manager", desc: "Assignments, revision, and reminders." },
  { href: "/calendar", icon: CalendarDays, title: "Calendar", desc: "Exams, holidays, tasks, and hostel leave." },
  { href: "/leave", icon: Home, title: "Hostel leave", desc: "Apply for leave from this application." },
  { href: "/attendance", icon: ClipboardCheck, title: "Attendance", desc: "Course-wise % from the academic database." },
  { href: "/marks", icon: GraduationCap, title: "Marks & grades", desc: "CAT, assignment, and lab internals." },
  { href: "/forecast", icon: TrendingUp, title: "Forecast", desc: "Will you stay above 75%? Predicted internals." },
  { href: "/timetable", icon: CalendarRange, title: "Timetable", desc: "This week’s classes and labs." },
];

const FACULTY_TOOLS = [
  { href: "/chat", icon: MessageCircle, title: "AI assistant", desc: "Draft circulars and check academic calendar." },
  { href: "/calendar", icon: CalendarDays, title: "Calendar", desc: "Department meetings and assessments." },
  { href: "/faculty", icon: ClipboardCheck, title: "Availability", desc: "Office hours published to students." },
  { href: "/drafts", icon: GraduationCap, title: "Recurring drafts", desc: "Weekly reminders and meeting invites." },
];

type Today = {
  source?: string;
  uis_linked?: boolean;
  uis_username?: string;
  next_class?: Record<string, unknown> | null;
  fee_due?: { title?: string; remaining?: number; deadline?: string; status?: string } | null;
  unread_messages?: number;
  leave_status?: { status?: string; from?: string; to?: string; reason?: string } | null;
};

function WorkspaceInner() {
  const { user } = useAuth();
  const student = user?.role === "student";
  const hosteller = !!user?.is_hosteller || user?.residence_type === "hostel";
  const [today, setToday] = useState<Today | null>(null);

  useEffect(() => {
    if (!student) return;
    apiGet<Today>("/api/me/today")
      .then(setToday)
      .catch(() => setToday(null));
  }, [student]);

  const tools = student
    ? STUDENT_TOOLS.filter((t) => (t.href === "/leave" ? hosteller : true))
    : FACULTY_TOOLS;
  const nc = today?.next_class as { course?: string; subject?: string; time?: string; day?: string; slot?: string } | null | undefined;

  return (
    <CopilotShell title="Campus-GPT">
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <p className="text-sm text-primary font-medium capitalize">{user?.role} copilot</p>
          {student && <SyncBadge source={today?.source} />}
        </div>
        <h1 className="text-3xl font-bold text-primary mt-1">
          {student ? "Today" : "Ask · Understand · Decide · Create · Act"}
        </h1>
        <p className="text-gray-600 mt-2 mb-6">
          {student
            ? "Your next class, dues, messages, and leave — in one place."
            : "Faculty tools stay inside your assigned scope."}
        </p>

        {student && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
            <Link href="/timetable" className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/30">
              <p className="text-[11px] uppercase text-gray-400">Next class</p>
              <p className="font-semibold text-primary mt-1 text-sm">
                {nc?.course || nc?.subject || nc?.slot || "Open timetable"}
              </p>
              <p className="text-xs text-gray-500 mt-1">{nc?.time || nc?.day || "—"}</p>
            </Link>
            <Link href="/fees" className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/30">
              <p className="text-[11px] uppercase text-gray-400">Fee due</p>
              {today?.fee_due ? (
                <>
                  <p className="font-semibold text-primary mt-1 text-sm">{today.fee_due.title}</p>
                  <p className="text-xs text-amber-700 mt-1">
                    ₹{today.fee_due.remaining} · due {today.fee_due.deadline || "soon"}
                  </p>
                </>
              ) : (
                <p className="text-sm text-gray-500 mt-2">No outstanding fees</p>
              )}
            </Link>
            <Link href="/messages" className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/30">
              <p className="text-[11px] uppercase text-gray-400">Messages</p>
              <p className="font-semibold text-primary mt-1 text-2xl">{today?.unread_messages ?? 0}</p>
              <p className="text-xs text-gray-500">unread notifications</p>
            </Link>
            {hosteller ? (
              <Link href="/leave" className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/30">
                <p className="text-[11px] uppercase text-gray-400">Leave status</p>
                {today?.leave_status ? (
                  <>
                    <p className="font-semibold text-primary mt-1 text-sm capitalize">{today.leave_status.status}</p>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{today.leave_status.reason || "Latest request"}</p>
                  </>
                ) : (
                  <p className="text-sm text-gray-500 mt-2">No recent leave — apply here</p>
                )}
              </Link>
            ) : (
              <Link href="/fees" className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/30">
                <p className="text-[11px] uppercase text-gray-400">Residence</p>
                <p className="font-semibold text-primary mt-1 text-sm capitalize">
                  {(user?.residence_type || "day_scholar").replace("_", " ")}
                </p>
                <p className="text-xs text-gray-500 mt-1">Hostel leave applies to hostellers only</p>
              </Link>
            )}
          </div>
        )}

        {student && today && (
          <p className="text-xs text-gray-500 mb-4">
            UIS link:{" "}
            {today.uis_linked ? (
              <span className="text-emerald-700 font-medium">{today.uis_username}</span>
            ) : (
              <Link href="/settings" className="text-primary underline">
                Connect in Settings
              </Link>
            )}
          </p>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {tools.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className="p-5 rounded-2xl bg-white border border-[#7C5AED]/15 hover:border-primary/40 hover:shadow-lg transition-all"
            >
              <t.icon className="w-7 h-7 text-primary mb-3" />
              <h2 className="font-semibold text-primary">{t.title}</h2>
              <p className="text-sm text-gray-600 mt-1">{t.desc}</p>
            </Link>
          ))}
        </div>
      </main>
    </CopilotShell>
  );
}

export default function WorkspacePage() {
  return (
    <RequireAuth>
      <WorkspaceInner />
    </RequireAuth>
  );
}
