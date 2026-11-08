"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Assessment = { assessment: string; score: number; max_score: number };
type CourseMarks = {
  course_code: string;
  course_title: string;
  section: string;
  grade?: string | null;
  grade_point?: number | null;
  assessments: Assessment[];
};
type Achievement = {
  id: number;
  title: string;
  category: string;
  description: string;
  awarded_on?: string | null;
};
type RosterRow = {
  student_id: string;
  name: string;
  email: string;
  year: number;
  semester: number;
  section: string;
  batch: string;
  cgpa: number;
  attendance: number;
  program?: string | null;
  department_code?: string | null;
  is_active: boolean;
  marks: CourseMarks[];
  achievements: Achievement[];
  marks_count: number;
  achievements_count: number;
};

export default function AdminViewStudentsPage() {
  const [items, setItems] = useState<RosterRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [year, setYear] = useState("");
  const [department, setDepartment] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(
    async (search = q, yr = year, dept = department) => {
      setBusy(true);
      setErr("");
      try {
        const params = new URLSearchParams({ limit: "100" });
        if (search.trim()) params.set("q", search.trim());
        if (yr) params.set("year", yr);
        if (dept) params.set("department", dept);
        const d = await apiFetch<{ items: RosterRow[]; total: number }>(
          `/api/v1/admin/students/roster?${params}`
        );
        setItems(d.items || []);
        setTotal(d.total ?? d.items?.length ?? 0);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load roster");
      } finally {
        setBusy(false);
      }
    },
    [q, year, department]
  );

  useEffect(() => {
    load("", "", "").catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    load();
  };

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#0B2A4A]">View students</h1>
          <p className="text-sm text-slate-500">
            Full roster with marks and achievements for every student
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href="/admin/students" className="px-3 py-2 rounded-lg border text-[#0B2A4A]">
            Filters / edit
          </Link>
          <Link href="/admin" className="px-3 py-2 rounded-lg border text-slate-600">
            Dashboard
          </Link>
        </div>
      </div>

      <form onSubmit={onSearch} className="flex flex-wrap gap-2 mb-4">
        <input
          className="border rounded-lg px-3 py-2 text-sm min-w-[220px]"
          placeholder="Search ID / name / email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="border rounded-lg px-3 py-2 text-sm" value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="">All years</option>
          {[1, 2, 3, 4].map((y) => (
            <option key={y} value={y}>
              Year {y}
            </option>
          ))}
        </select>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
        >
          <option value="">All departments</option>
          {["CSE", "ECE", "EEE", "MECH", "CIVIL"].map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <button type="submit" disabled={busy} className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm disabled:opacity-50">
          Search
        </button>
        <p className="text-sm text-slate-500 self-center">
          {total} student{total === 1 ? "" : "s"}
        </p>
      </form>

      {err && <p className="text-sm text-red-600 mb-3">{err}</p>}

      <div className="space-y-2">
        {items.map((s) => {
          const open = expanded === s.student_id;
          return (
            <div key={s.student_id} className="bg-white border rounded-xl shadow-sm overflow-hidden">
              <button
                type="button"
                className="w-full text-left px-4 py-3 flex flex-wrap items-center justify-between gap-2 hover:bg-slate-50"
                onClick={() => setExpanded(open ? null : s.student_id)}
              >
                <div>
                  <p className="font-semibold text-[#0B2A4A]">
                    {s.name}{" "}
                    <span className="text-xs font-normal text-slate-500">({s.student_id})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    {s.program || "—"} · Y{s.year}/S{s.semester} Sec {s.section} · Batch {s.batch} · CGPA{" "}
                    {s.cgpa} · Att {s.attendance}%
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="px-2 py-1 rounded border bg-sky-50 text-sky-800 border-sky-100">
                    {s.marks_count} mark{s.marks_count === 1 ? "" : "s"}
                  </span>
                  <span className="px-2 py-1 rounded border bg-amber-50 text-amber-900 border-amber-100">
                    {s.achievements_count} achievement{s.achievements_count === 1 ? "" : "s"}
                  </span>
                  <span className="px-2 py-1 rounded border text-slate-600">{open ? "Hide" : "View"}</span>
                </div>
              </button>

              {open && (
                <div className="border-t px-4 py-4 grid lg:grid-cols-2 gap-4 text-sm">
                  <div>
                    <h3 className="text-xs font-semibold uppercase text-slate-500 mb-2">Marks</h3>
                    {!s.marks?.length && <p className="text-slate-400 text-xs">No marks on record.</p>}
                    <div className="space-y-2">
                      {(s.marks || []).map((c) => (
                        <div key={`${c.course_code}-${c.section}`} className="border rounded-lg p-3 bg-slate-50">
                          <p className="font-medium text-[#0B2A4A]">
                            {c.course_code} · {c.course_title}
                            {c.grade ? ` · Grade ${c.grade}` : ""}
                          </p>
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {(c.assessments || []).map((a) => (
                              <span key={a.assessment} className="text-[11px] bg-white border rounded px-2 py-0.5">
                                {a.assessment}: {a.score}/{a.max_score}
                              </span>
                            ))}
                            {!c.assessments?.length && (
                              <span className="text-[11px] text-slate-400">Grade only</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold uppercase text-slate-500 mb-2">Achievements</h3>
                    {!s.achievements?.length && (
                      <p className="text-slate-400 text-xs">No achievements on record.</p>
                    )}
                    <ul className="space-y-2">
                      {(s.achievements || []).map((a) => (
                        <li key={a.id} className="border rounded-lg p-3 bg-amber-50/40">
                          <p className="font-medium text-[#0B2A4A]">{a.title}</p>
                          <p className="text-[11px] text-slate-500 capitalize">
                            {a.category}
                            {a.awarded_on ? ` · ${a.awarded_on}` : ""}
                          </p>
                          {a.description && (
                            <p className="text-xs text-slate-600 mt-1 whitespace-pre-wrap">{a.description}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p className="lg:col-span-2 text-xs text-slate-400">
                    Contact: {s.email}
                    {!s.is_active ? " · Inactive account" : ""}
                  </p>
                </div>
              )}
            </div>
          );
        })}
        {!items.length && !busy && (
          <p className="text-sm text-slate-400 text-center py-10 border rounded-xl bg-white">No students found.</p>
        )}
      </div>
    </AppShell>
  );
}
