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
  percentage: number;
  status: string;
};

const STATUSES = ["", "P", "A", "OD", "ML", "RH", "EH"];

export default function FacultyAttendancePage() {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [offeringId, setOfferingId] = useState<number | null>(null);
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [slot, setSlot] = useState("Hour 1");
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

  const load = async (offering: number, day: string, slotName: string) => {
    const data = await apiFetch<{ students: Row[] }>(
      `/api/v1/faculty/classes/${offering}/register?entry_date=${day}&slot_name=${encodeURIComponent(slotName)}`
    );
    setRows(data.students || []);
  };

  useEffect(() => {
    if (!offeringId) return;
    setErr("");
    load(offeringId, entryDate, slot).catch((e) => setErr(e.message));
  }, [offeringId]);

  const save = async () => {
    if (!offeringId) return;
    setErr("");
    setMessage("");
    const filled = rows.filter((row) => row.status);
    const result = await apiFetch<{ saved: number }>(`/api/v1/faculty/classes/${offeringId}/register`, {
      method: "POST",
      body: JSON.stringify({
        entry_date: entryDate,
        slot_name: slot,
        rows: filled.map((row) => ({ student_id: row.student_id, status: row.status })),
      }),
    });
    setMessage(`Saved attendance for ${result.saved} student${result.saved === 1 ? "" : "s"}.`);
    await load(offeringId, entryDate, slot);
  };

  const current = classes.find((item) => item.offering_id === offeringId);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Attendance entry</h1>
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
            Date
            <input className="mt-1 block border rounded px-2 py-1" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
          </label>
          <label className="text-sm text-slate-600">
            Slot
            <input className="mt-1 block border rounded px-2 py-1" value={slot} onChange={(e) => setSlot(e.target.value)} />
          </label>
          <button
            type="button"
            className="border rounded px-3 py-1.5 text-sm"
            onClick={() => offeringId && load(offeringId, entryDate, slot).catch((e) => setErr(e.message))}
          >
            Load
          </button>
          <button type="button" className="bg-[#0B2A4A] text-white rounded px-3 py-1.5 text-sm" onClick={() => save().catch((e) => setErr(e.message))}>
            Save attendance
          </button>
        </div>
        {current ? (
          <p className="px-4 py-2 text-sm text-slate-600">
            {current.title}. Only students mapped to section {current.section} of this course are listed.
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
                <th className="px-3 py-2">Attendance %</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.student_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{row.sno || index + 1}</td>
                  <td className="px-3 py-2 font-medium">{row.student_id}</td>
                  <td className="px-3 py-2">{row.name}</td>
                  <td className="px-3 py-2">{row.section}</td>
                  <td className="px-3 py-2">{Number(row.percentage || 0).toFixed(1)}</td>
                  <td className="px-3 py-2">
                    <select
                      className="border rounded px-2 py-1"
                      value={row.status || ""}
                      onChange={(e) =>
                        setRows((prev) => prev.map((item) => (item.student_id === row.student_id ? { ...item, status: e.target.value } : item)))
                      }
                    >
                      {STATUSES.map((code) => (
                        <option key={code || "blank"} value={code}>
                          {code || "—"}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
              {classes.length && !rows.length ? (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-slate-500">
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
