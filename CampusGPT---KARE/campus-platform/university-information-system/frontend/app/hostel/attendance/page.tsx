"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Row = {
  sno: number;
  student_id: string;
  name: string;
  section: string;
  hostel: string;
  block: string;
  room: string;
  bed: string;
  status: string;
};

export default function HostelAttendancePage() {
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<Row[]>([]);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");

  const load = async (day: string) => {
    const data = await apiFetch<{ students: Row[] }>(`/api/v1/hostel/attendance?entry_date=${day}`);
    setRows(data.students || []);
  };

  useEffect(() => {
    load(entryDate).catch((e) => setErr(e.message));
  }, []);

  const save = async () => {
    setErr("");
    setMessage("");
    const filled = rows.filter((row) => row.status === "P" || row.status === "A");
    const result = await apiFetch<{ saved: number }>("/api/v1/hostel/attendance", {
      method: "POST",
      body: JSON.stringify({
        entry_date: entryDate,
        rows: filled.map((row) => ({ student_id: row.student_id, status: row.status })),
      }),
    });
    setMessage(`Saved attendance for ${result.saved} inmate${result.saved === 1 ? "" : "s"}.`);
    await load(entryDate);
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Inmate attendance</h1>
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-600">
            Date
            <input className="mt-1 block border rounded px-2 py-1" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
          </label>
          <button type="button" className="border rounded px-3 py-1.5 text-sm" onClick={() => load(entryDate).catch((e) => setErr(e.message))}>
            Load
          </button>
          <button type="button" className="bg-[#0B2A4A] text-white rounded px-3 py-1.5 text-sm" onClick={() => save().catch((e) => setErr(e.message))}>
            Save attendance
          </button>
        </div>
        <p className="px-4 py-2 text-sm text-slate-600">Only students allocated to a hostel room are listed.</p>
        {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
        {message ? <p className="px-4 py-2 text-sm text-emerald-700">{message}</p> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">S.No</th>
                <th className="px-3 py-2">Register number</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Block</th>
                <th className="px-3 py-2">Room</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.student_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{row.sno}</td>
                  <td className="px-3 py-2">
                    <Link href={`/hostel/students/${row.student_id}`} className="font-medium text-[#0B2A4A] underline">
                      {row.student_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    <Link href={`/hostel/students/${row.student_id}`} className="text-[#0B2A4A] underline">
                      {row.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2">{row.block}</td>
                  <td className="px-3 py-2">{row.room}</td>
                  <td className="px-3 py-2">
                    <select
                      className="border rounded px-2 py-1"
                      value={row.status || ""}
                      onChange={(e) =>
                        setRows((prev) => prev.map((item) => (item.student_id === row.student_id ? { ...item, status: e.target.value } : item)))
                      }
                    >
                      <option value="">—</option>
                      <option value="P">Present</option>
                      <option value="A">Absent</option>
                    </select>
                  </td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-slate-500">
                    No hostel inmates are allocated.
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
