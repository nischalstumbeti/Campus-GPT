"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Leave = {
  id: number;
  student_id: string;
  student_name: string;
  section: string;
  from: string;
  to: string;
  reason: string;
  destination: string;
  status: string;
  source: string;
};

export default function FacultyLeavesPage() {
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () =>
    apiFetch<{ leaves: Leave[] }>("/api/v1/faculty/leaves")
      .then((d) => setLeaves(d.leaves || []))
      .catch(() => setLeaves([]));

  useEffect(() => {
    load();
  }, []);

  const setStatus = async (id: number, status: "approved" | "rejected") => {
    setMsg("");
    setErr("");
    try {
      const res = await apiFetch<{ email_sent?: boolean }>(`/api/v1/faculty/leaves/${id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      setMsg(
        `Leave #${id} ${status}. ` +
          (res.email_sent
            ? "Student was emailed the request details and status."
            : "Status saved (email skipped if SMTP is not configured).")
      );
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-[#0B2A4A] mb-1">Student leave</h1>
      <p className="text-sm text-slate-500 mb-4">
        Approve or reject leave for students in your classes. The student receives an email with request details and status.
      </p>
      {err && <p className="text-sm text-red-700 mb-3">{err}</p>}
      {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}
      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Dates</th>
              <th className="px-3 py-2">Reason / destination</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {leaves.map((l) => (
              <tr key={l.id} className="border-t">
                <td className="px-3 py-2">
                  <p className="font-medium">{l.student_name}</p>
                  <p className="text-xs text-slate-500">
                    {l.student_id} · Sec {l.section}
                  </p>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {l.from} → {l.to}
                </td>
                <td className="px-3 py-2">
                  {l.reason}
                  {l.destination ? <span className="text-xs text-slate-500 block">{l.destination}</span> : null}
                </td>
                <td className="px-3 py-2 capitalize text-xs">{l.source}</td>
                <td
                  className={`px-3 py-2 capitalize text-xs font-medium ${
                    l.status === "approved"
                      ? "text-emerald-700"
                      : l.status === "rejected"
                        ? "text-red-600"
                        : "text-amber-700"
                  }`}
                >
                  {l.status}
                </td>
                <td className="px-3 py-2 whitespace-nowrap space-x-2">
                  {l.status === "pending" ? (
                    <>
                      <button
                        type="button"
                        className="text-xs font-semibold text-emerald-700"
                        onClick={() => setStatus(l.id, "approved")}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-red-600"
                        onClick={() => setStatus(l.id, "rejected")}
                      >
                        Reject
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>
              </tr>
            ))}
            {!leaves.length && (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-slate-400">
                  No leave records for your students yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
