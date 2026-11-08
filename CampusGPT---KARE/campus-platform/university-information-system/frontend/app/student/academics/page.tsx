"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type CourseRow = {
  code: string;
  title: string;
  credits: number;
  semester: number;
  result_group: string;
  letter: string;
  grade_point: number | null;
};

type Semester = {
  semester: number;
  credits: number;
  sgpa: number | null;
  courses: CourseRow[];
};

type Academics = {
  cgpa: number;
  credits_completed: number;
  credits_required: number;
  backlogs: number;
  semesters: Semester[];
  non_cgpa: CourseRow[];
  mandatory: CourseRow[];
};

const TABS = [
  { id: "semester", label: "Semester wise" },
  { id: "overall", label: "Overall" },
  { id: "non_cgpa", label: "Non CGPA" },
  { id: "mandatory", label: "Mandatory courses" },
] as const;

function CourseTable({ rows, showSemester = false }: { rows: CourseRow[]; showSemester?: boolean }) {
  if (!rows.length) {
    return <p className="px-4 py-3 text-sm text-slate-500">No courses in this group.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-left text-xs text-slate-500">
        <tr>
          {showSemester ? <th className="px-3 py-2">Semester</th> : null}
          <th className="px-3 py-2">Code</th>
          <th className="px-3 py-2">Course</th>
          <th className="px-3 py-2">Credits</th>
          <th className="px-3 py-2">Grade</th>
          <th className="px-3 py-2">Grade point</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.semester}-${row.code}`} className="border-t">
            {showSemester ? <td className="px-3 py-2">{row.semester}</td> : null}
            <td className="px-3 py-2 font-medium">{row.code}</td>
            <td className="px-3 py-2">{row.title}</td>
            <td className="px-3 py-2">{row.credits}</td>
            <td className="px-3 py-2">{row.letter || "—"}</td>
            <td className="px-3 py-2">{row.grade_point ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AcademicsPage() {
  const [data, setData] = useState<Academics | null>(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("semester");

  useEffect(() => {
    apiFetch<Academics>("/api/v1/student/academics")
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Could not load academics"));
  }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-4">My Academics</h1>
      {err && <p className="text-sm text-red-600 mb-3">{err}</p>}
      <div className="flex flex-wrap gap-2 mb-4">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`px-3 py-2 rounded-lg text-sm ${tab === item.id ? "bg-brand text-white" : "border bg-white"}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {data && tab === "overall" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-white border rounded-lg p-4">
              <p className="text-xs text-slate-500">CGPA</p>
              <p className="text-2xl font-semibold text-brand">{data.cgpa}</p>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <p className="text-xs text-slate-500">Credits</p>
              <p className="text-2xl font-semibold text-brand">
                {data.credits_completed} / {data.credits_required}
              </p>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <p className="text-xs text-slate-500">Backlogs</p>
              <p className="text-2xl font-semibold text-brand">{data.backlogs}</p>
            </div>
            <div className="bg-white border rounded-lg p-4">
              <p className="text-xs text-slate-500">Semesters</p>
              <p className="text-2xl font-semibold text-brand">{data.semesters.length}</p>
            </div>
          </div>
          <div className="bg-white border overflow-hidden">
            <h2 className="uis-panel-title">Semester summary</h2>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2">Semester</th>
                  <th className="px-3 py-2">CGPA credits</th>
                  <th className="px-3 py-2">SGPA</th>
                </tr>
              </thead>
              <tbody>
                {data.semesters.map((semester) => (
                  <tr key={semester.semester} className="border-t">
                    <td className="px-3 py-2">Semester {semester.semester}</td>
                    <td className="px-3 py-2">{semester.credits}</td>
                    <td className="px-3 py-2">{semester.sgpa ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data && tab === "semester" && (
        <div className="space-y-4">
          {data.semesters.map((semester) => (
            <section key={semester.semester} className="uis-panel">
              <h2 className="uis-panel-title flex justify-between">
                <span>Semester {semester.semester}</span>
                <span>
                  SGPA {semester.sgpa ?? "—"} · {semester.credits} credits
                </span>
              </h2>
              <CourseTable rows={semester.courses.filter((row) => row.result_group === "cgpa")} />
            </section>
          ))}
        </div>
      )}

      {data && tab === "non_cgpa" && (
        <section className="uis-panel">
          <h2 className="uis-panel-title">Non CGPA courses</h2>
          <p className="px-4 py-2 text-xs text-slate-500">These courses are completed and are not included in CGPA.</p>
          <CourseTable rows={data.non_cgpa} showSemester />
        </section>
      )}

      {data && tab === "mandatory" && (
        <section className="uis-panel">
          <h2 className="uis-panel-title">Mandatory courses</h2>
          <p className="px-4 py-2 text-xs text-slate-500">Required courses that do not add to CGPA.</p>
          <CourseTable rows={data.mandatory} showSemester />
        </section>
      )}
    </AppShell>
  );
}
