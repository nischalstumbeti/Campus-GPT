"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

function AcademicsInner() {
  const [grad, setGrad] = useState<{ percent: number; credits_completed: number; credits_required: number; remaining: string[]; internship: string; project: string; disclaimer: string } | null>(null);
  useEffect(() => {
    apiGet<{ percent: number; credits_completed: number; credits_required: number; remaining: string[]; internship: string; project: string; disclaimer: string }>("/api/copilot/graduation")
      .then(setGrad)
      .catch(() => setGrad(null));
  }, []);

  const links = [
    { href: "/attendance", label: "Attendance" },
    { href: "/marks", label: "Marks" },
    { href: "/forecast", label: "Forecast" },
    { href: "/timetable", label: "Timetable" },
  ];

  return (
    <CopilotShell title="My Academic Life">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">My Academic Life</h1>
        <p className="text-sm text-gray-600 mt-1">Authorized records only. Facts vs calculations are labeled.</p>
        <div className="grid grid-cols-2 gap-3 mt-6">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="p-4 rounded-2xl border border-[#7C5AED]/15 bg-white font-medium text-primary">
              {l.label}
            </Link>
          ))}
        </div>
        {grad && (
          <section className="mt-8 rounded-2xl border border-gray-100 bg-white p-5">
            <h2 className="font-semibold text-primary">Graduation progress</h2>
            <p className="text-xs text-gray-500 mt-1">{grad.disclaimer}</p>
            <div className="mt-3 h-3 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-full bg-primary" style={{ width: `${Math.min(grad.percent, 100)}%` }} />
            </div>
            <p className="text-sm mt-2">{grad.credits_completed} / {grad.credits_required} credits · {grad.percent}%</p>
            <p className="text-sm text-gray-600 mt-2">Internship: {grad.internship} · Project: {grad.project}</p>
            <ul className="mt-3 text-sm list-disc pl-5 text-gray-700">
              {(grad.remaining || []).map((r) => <li key={r}>{r}</li>)}
            </ul>
          </section>
        )}
      </main>
    </CopilotShell>
  );
}

export default function AcademicsPage() {
  return <RequireAuth roles={["student"]}><AcademicsInner /></RequireAuth>;
}
