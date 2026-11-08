"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type ExamRow = {
  id: number;
  code: string;
  course: string;
  type: string;
  date: string;
  start: string;
  venue: string;
};

function showDate(iso: string) {
  const [year, month, day] = iso.split("-");
  if (!day) return iso;
  return `${day}/${month}/${year}`;
}

export default function ExamsPage() {
  const [rows, setRows] = useState<ExamRow[]>([]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ exams: ExamRow[] }>("/api/v1/student/exams")
      .then((data) => setRows(data.exams || []))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Answer Script</h1>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Course</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">Venue</th>
              <th className="px-3 py-2">Answer script</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((exam) => (
              <tr key={exam.id} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  {exam.code} · {exam.course}
                </td>
                <td className="px-3 py-2">{exam.type}</td>
                <td className="px-3 py-2">
                  {showDate(exam.date)} {exam.start}
                </td>
                <td className="px-3 py-2">{exam.venue}</td>
                <td className="px-3 py-2">
                  <button type="button" className="text-brand font-medium hover:underline" onClick={() => setOpen(true)}>
                    View
                  </button>
                </td>
              </tr>
            ))}
            {!rows.length && !err ? (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-slate-500">
                  No answer scripts are scheduled.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
      {open ? (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white w-full max-w-md p-5 shadow-lg" onClick={(event) => event.stopPropagation()}>
            <h2 className="text-lg font-semibold text-brand">Answer script</h2>
            <p className="mt-3 text-sm text-slate-700">
              Please wait. We will notify you when the answer script is uploaded. You can view it then.
            </p>
            <button type="button" className="mt-4 px-3 py-1.5 rounded bg-brand text-white text-sm" onClick={() => setOpen(false)}>
              OK
            </button>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
