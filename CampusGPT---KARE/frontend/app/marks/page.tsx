"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Row = {
  course_code: string;
  course_name: string;
  assessment: string;
  marks: number;
  max_marks: number;
  percentage: number;
  recorded_on: string;
};

export default function MarksPage() {
  return (
    <RequireAuth roles={["student"]}>
      <MarksInner />
    </RequireAuth>
  );
}

function MarksInner() {
  const [rows, setRows] = useState<Row[]>([]);
  const [label, setLabel] = useState("");

  useEffect(() => {
    apiGet<{ student?: { full_name: string; roll_no: string }; records: Row[] }>("/api/academic/marks")
      .then((d) => {
        setRows(d.records || []);
        if (d.student) setLabel(`${d.student.full_name} · ${d.student.roll_no}`);
      })
      .catch(() => setRows([]));
  }, []);

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-5xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary">Internal marks</h1>
        <p className="text-sm text-gray-600 mb-6">{label} · Pulled from the academic database</p>
        <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-primary/5 text-primary">
              <tr>
                <th className="p-3 text-left">Course</th>
                <th className="p-3 text-left">Assessment</th>
                <th className="p-3 text-left">Marks</th>
                <th className="p-3 text-left">%</th>
                <th className="p-3 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.course_code}-${r.assessment}-${i}`} className="border-t border-gray-50">
                  <td className="p-3">
                    <span className="font-medium">{r.course_code}</span>
                    <span className="text-gray-500 text-xs block">{r.course_name}</span>
                  </td>
                  <td className="p-3">{r.assessment}</td>
                  <td className="p-3">{r.marks}/{r.max_marks}</td>
                  <td className={`p-3 font-semibold ${r.percentage < 70 ? "text-amber-700" : "text-primary"}`}>{r.percentage}%</td>
                  <td className="p-3 text-gray-500">{r.recorded_on}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}
