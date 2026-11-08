"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Row = {
  course_code: string;
  course_name: string;
  conducted: number;
  present: number;
  od: number;
  percentage: number;
  status: string;
};

export default function AttendancePage() {
  return (
    <RequireAuth roles={["student"]}>
      <AttendanceInner />
    </RequireAuth>
  );
}

function AttendanceInner() {
  const [rows, setRows] = useState<Row[]>([]);
  const [label, setLabel] = useState("");

  useEffect(() => {
    apiGet<{ student?: { full_name: string; roll_no: string }; records: Row[] }>("/api/academic/attendance")
      .then((d) => {
        setRows(d.records || []);
        if (d.student) setLabel(`${d.student.full_name} · ${d.student.roll_no}`);
      })
      .catch(() => setRows([]));
  }, []);

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-4xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary">Attendance</h1>
        <p className="text-sm text-gray-600 mb-6">{label} · Minimum 75% to appear for end-semester exams</p>
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.course_code} className="p-4 rounded-2xl border border-gray-100 bg-white">
              <div className="flex justify-between gap-3">
                <div>
                  <p className="font-semibold text-primary">{r.course_code} · {r.course_name}</p>
                  <p className="text-xs text-gray-500">Present {r.present} + OD {r.od} / {r.conducted} conducted</p>
                </div>
                <span className={`text-sm font-semibold ${r.percentage < 75 ? "text-red-600" : r.percentage < 80 ? "text-amber-600" : "text-green-700"}`}>
                  {r.percentage}% · {r.status}
                </span>
              </div>
              <div className="mt-2 h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className={`h-full ${r.percentage < 75 ? "bg-red-500" : r.percentage < 80 ? "bg-amber-500" : "bg-primary"}`}
                  style={{ width: `${Math.min(r.percentage, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}
