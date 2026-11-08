"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiDownload, apiFetch } from "@/lib/api";

type WindowRow = { kind: string; enabled: boolean; note: string; fee: number };
type Application = {
  id: number;
  source: string;
  kind: string;
  status: string;
  student_id: string;
  name: string;
  section: string;
  batch: string;
  code: string;
  course: string;
};

const LABELS: Record<string, string> = {
  revaluation: "Revaluation",
  arrear: "Arrear",
  backlog: "Backlog",
  registration: "Course registration",
  withdrawal: "Course withdrawal",
  makeup: "Make-up",
};

export default function AdminApplicationsPage() {
  const [windows, setWindows] = useState<WindowRow[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [service, setService] = useState("all");

  const load = () => {
    apiFetch<{ windows: WindowRow[]; applications: Application[] }>("/api/v1/admin/applications")
      .then((data) => {
        setWindows(data.windows || []);
        setApplications(data.applications || []);
      })
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (row: WindowRow) => {
    setErr("");
    setMsg("");
    try {
      await apiFetch(`/api/v1/admin/applications/${row.kind}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: row.enabled, note: row.note, fee: Number(row.fee) || 0 }),
      });
      setMsg(`${LABELS[row.kind] || row.kind} ${row.enabled ? "opened" : "closed"}.`);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    }
  };

  const update = (kind: string, patch: Partial<WindowRow>) => {
    setWindows((rows) => rows.map((row) => (row.kind === kind ? { ...row, ...patch } : row)));
  };

  const visible = applications.filter((row) => service === "all" || row.kind === service);

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Exam applications</h1>
        <p className="px-4 py-3 text-sm text-slate-600">
          Students can apply only while that option is enabled here. Course registration lists the courses mapped to the student's section.
        </p>
        {err ? <p className="px-4 pb-2 text-sm text-red-600">{err}</p> : null}
        {msg ? <p className="px-4 pb-2 text-sm text-brand">{msg}</p> : null}
        <div className="grid gap-3 p-4 md:grid-cols-3">
          {windows.map((row) => (
            <div key={row.kind} className="border border-slate-200 p-3">
              <h2 className="font-semibold text-brand">{LABELS[row.kind] || row.kind}</h2>
              <label className="mt-3 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  onChange={(e) => update(row.kind, { enabled: e.target.checked })}
                />
                Enable student applications
              </label>
              <label className="block mt-3 text-xs text-slate-500">
                Note shown to students
                <textarea
                  className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800"
                  rows={3}
                  value={row.note}
                  onChange={(e) => update(row.kind, { note: e.target.value })}
                />
              </label>
              <label className="block mt-3 text-xs text-slate-500">
                Fee (₹)
                <input
                  type="number"
                  min={0}
                  className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800"
                  value={row.fee}
                  onChange={(e) => update(row.kind, { fee: Number(e.target.value) })}
                />
              </label>
              <button type="button" className="mt-3 px-3 py-1.5 rounded bg-brand text-white text-sm" onClick={() => save(row)}>
                Save
              </button>
            </div>
          ))}
        </div>
      </section>
      <section className="uis-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-slate-100">
          <h2 className="font-semibold text-[#0B2A4A]">Submitted applications</h2>
          <div className="flex flex-wrap items-center gap-2">
            <select className="border rounded px-2 py-1.5 text-sm" value={service} onChange={(e) => setService(e.target.value)}>
              <option value="all">All services</option>
              {Object.entries(LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <button
              type="button"
              className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm"
              onClick={() =>
                apiDownload(
                  `/api/v1/admin/applications/export?kind=${service}`,
                  service === "all" ? "applied-services.xlsx" : `applied-${service}.xlsx`
                ).catch((e) => setErr(e.message))
              }
            >
              Download Excel
            </button>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Course</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={`${row.source}-${row.id}`} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  {row.name} · {row.student_id}
                </td>
                <td className="px-3 py-2 capitalize">{row.kind}</td>
                <td className="px-3 py-2">
                  {row.code} · {row.course}
                </td>
                <td className="px-3 py-2 capitalize">{row.status}</td>
              </tr>
            ))}
            {!visible.length ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-slate-500">
                  No applications yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
