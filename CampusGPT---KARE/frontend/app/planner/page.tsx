"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Plan = {
  student?: { full_name: string; roll_no: string };
  suggestions?: string[];
  free_blocks?: { day: string; start_time: string; end_time: string; use: string }[];
  upcoming_exams?: { title: string; start_date: string; end_date: string }[];
  office_hours?: { faculty: string; day: string; start_time: string; end_time: string; location: string }[];
  focus_attendance?: { course_code: string; course_name: string; percentage: number }[];
};

export default function PlannerPage() {
  return (
    <RequireAuth roles={["student"]}>
      <PlannerInner />
    </RequireAuth>
  );
}

function PlannerInner() {
  const [plan, setPlan] = useState<Plan | null>(null);

  useEffect(() => {
    apiGet<Plan>("/api/academic/plan").then(setPlan).catch(() => setPlan(null));
  }, []);

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-5xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary">Plan from your academic schedule</h1>
        <p className="text-sm text-gray-600 mb-6">
          Combines timetable free slots, attendance risk, internals, exams, and faculty office hours.
        </p>
        {plan?.student && (
          <p className="mb-4 font-medium text-primary">{plan.student.full_name} · {plan.student.roll_no}</p>
        )}
        <section className="mb-6 p-5 rounded-2xl bg-white border border-primary/15">
          <h2 className="font-semibold text-primary mb-2">This week</h2>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            {(plan?.suggestions || []).map((s) => <li key={s}>{s}</li>)}
          </ul>
        </section>
        <div className="grid md:grid-cols-2 gap-5">
          <section className="p-5 rounded-2xl bg-white border border-gray-100">
            <h2 className="font-semibold text-primary mb-2">Free blocks</h2>
            {(plan?.free_blocks || []).map((b, i) => (
              <p key={i} className="text-sm text-gray-700">{b.day} {b.start_time}–{b.end_time} · {b.use}</p>
            ))}
          </section>
          <section className="p-5 rounded-2xl bg-white border border-gray-100">
            <h2 className="font-semibold text-primary mb-2">Meet faculty</h2>
            {(plan?.office_hours || []).map((o, i) => (
              <p key={i} className="text-sm text-gray-700">{o.faculty} · {o.day} {o.start_time} at {o.location}</p>
            ))}
          </section>
          <section className="p-5 rounded-2xl bg-white border border-gray-100">
            <h2 className="font-semibold text-primary mb-2">Attendance watch</h2>
            {(plan?.focus_attendance || []).map((a) => (
              <p key={a.course_code} className="text-sm">{a.course_code} {a.course_name} · {a.percentage}%</p>
            ))}
          </section>
          <section className="p-5 rounded-2xl bg-white border border-gray-100">
            <h2 className="font-semibold text-primary mb-2">Academic calendar</h2>
            {(plan?.upcoming_exams || []).map((e) => (
              <p key={e.title} className="text-sm">{e.title}: {e.start_date}{e.end_date ? ` – ${e.end_date}` : ""}</p>
            ))}
          </section>
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}
