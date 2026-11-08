"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type ClassItem = { offering_id: number; code: string; title: string; section: string; semester: number };
type Row = {
  sno: number;
  student_id: string;
  name: string;
  section: string;
  score: number | null;
};

export default function FacultyMarksPage() {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [offeringId, setOfferingId] = useState<number | null>(null);
  const [assessment, setAssessment] = useState("CAT-1");
  const [maxScore, setMaxScore] = useState("20");
  const [rows, setRows] = useState<Row[]>([]);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ classes: ClassItem[] }>("/api/v1/faculty/classes")
      .then((data) => {
        const list = data.classes || [];
        setClasses(list);
        setOfferingId(list[0]?.offering_id ?? null);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const load = async (offering: number, name: string) => {
    const data = await apiFetch<{ students: Row[] }>(
      `/api/v1/faculty/classes/${offering}/mark-sheet?assessment=${encodeURIComponent(name)}`
    );
    setRows(data.students || []);
  };

  useEffect(() => {
    if (!offeringId) return;
    load(offeringId, assessment).catch((e) => setErr(e.message));
  }, [offeringId]);

  const save = async () => {
    if (!offeringId) return;
    setErr("");
    setMessage("");
    const filled = rows.filter((row) => row.score !== null && row.score !== undefined && String(row.score) !== "");
    const result = await apiFetch<{ saved: number }>(`/api/v1/faculty/classes/${offeringId}/mark-sheet`, {
      method: "POST",
      body: JSON.stringify({
        assessment,
        max_score: Number(maxScore),
        rows: filled.map((row) => ({ student_id: row.student_id, score: Number(row.score) })),
      }),
    });
    setMessage(`Saved ${assessment} for ${result.saved} student${result.saved === 1 ? "" : "s"}.`);
    await load(offeringId, assessment);
  };

  const current = classes.find((item) => item.offering_id === offeringId);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Marks entry</h1>
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-600">
            Allocated class
            <select
              className="mt-1 block border rounded px-2 py-1 min-w-64"
              value={offeringId ?? ""}
              onChange={(e) => setOfferingId(Number(e.target.value))}
            >
              {classes.map((item) => (
                <option key={item.offering_id} value={item.offering_id}>
                  {item.code} · Section {item.section} · Sem {item.semester}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-slate-600">
            Assessment
            <input className="mt-1 block border rounded px-2 py-1" value={assessment} onChange={(e) => setAssessment(e.target.value)} />
          </label>
          <label className="text-sm text-slate-600">
            Max
            <input className="mt-1 block border rounded px-2 py-1 w-20" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
          </label>
          <button
            type="button"
            className="border rounded px-3 py-1.5 text-sm"
            onClick={() => offeringId && load(offeringId, assessment).catch((e) => setErr(e.message))}
          >
            Load
          </button>
          <button type="button" className="bg-[#0B2A4A] text-white rounded px-3 py-1.5 text-sm" onClick={() => save().catch((e) => setErr(e.message))}>
            Save marks
          </button>
        </div>
        {current ? (
          <p className="px-4 py-2 text-sm text-slate-600">
            {current.title}. Marks are stored only for students mapped to section {current.section}.
          </p>
        ) : null}
        {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
        {message ? <p className="px-4 py-2 text-sm text-emerald-700">{message}</p> : null}
        {!classes.length ? <p className="px-4 py-4 text-sm text-slate-600">No course section is allocated to you yet.</p> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">S.No</th>
                <th className="px-3 py-2">Register number</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Marks</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.student_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{row.sno || index + 1}</td>
                  <td className="px-3 py-2 font-medium">{row.student_id}</td>
                  <td className="px-3 py-2">{row.name}</td>
                  <td className="px-3 py-2">{row.section}</td>
                  <td className="px-3 py-2">
                    <input
                      className="border rounded px-2 py-1 w-24"
                      type="number"
                      min={0}
                      value={row.score ?? ""}
                      onChange={(e) =>
                        setRows((prev) =>
                          prev.map((item) =>
                            item.student_id === row.student_id
                              ? { ...item, score: e.target.value === "" ? null : Number(e.target.value) }
                              : item
                          )
                        )
                      }
                    />
                  </td>
                </tr>
              ))}
              {classes.length && !rows.length ? (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-slate-500">
                    No students are mapped to this course section.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
