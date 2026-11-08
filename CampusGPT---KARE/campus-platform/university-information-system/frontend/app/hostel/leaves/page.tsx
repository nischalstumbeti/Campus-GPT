"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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

export default function HostelLeavesPage() {
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [filter, setFilter] = useState("pending");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = (status: string) => {
    const q = status === "all" ? "" : `?status=${status}`;
    apiFetch<{ leaves: Leave[] }>(`/api/v1/hostel/leaves${q}`)
      .then((d) => setLeaves(d.leaves || []))
      .catch(() => setLeaves([]));
  };

  useEffect(() => {
    load(filter);
  }, [filter]);

  const setStatus = async (id: number, status: "approved" | "rejected") => {
    setMsg("");
    setErr("");
    try {
      const res = await apiFetch<{ email_sent?: boolean }>(`/api/v1/hostel/leaves/${id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      setMsg(
        `Leave #${id} marked ${status}. Student and faculty see it in UIS/Campus-GPT` +
          (res.email_sent ? "; student emailed with request details and status." : ".")
      );
      load(filter);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <AppShell>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#0B2A4A]">Hostel leave queue</h1>
          <p className="text-sm text-slate-500">Applications from Campus-GPT and UIS appear here for warden action.</p>
        </div>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
      </div>
      {err && <p className="text-sm text-red-700 mb-3">{err}</p>}
      {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}
      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Dates</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {leaves.map((l) => (
              <tr key={l.id} className="border-t align-top">
                <td className="px-3 py-2">
                  <Link href={`/hostel/students/${l.student_id}`} className="font-medium text-[#0B2A4A] underline">
                    {l.student_name}
                  </Link>
                  <p className="text-xs">
                    <Link href={`/hostel/students/${l.student_id}`} className="text-[#0B2A4A] underline">
                      {l.student_id}
                    </Link>
                    <span className="text-slate-500"> · Sec {l.section}</span>
                  </p>
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {l.from} → {l.to}
                  {l.destination ? <p className="text-xs text-slate-500">{l.destination}</p> : null}
                </td>
                <td className="px-3 py-2">{l.reason}</td>
                <td className="px-3 py-2 capitalize text-xs">{l.source}</td>
                <td className="px-3 py-2 capitalize">{l.status}</td>
                <td className="px-3 py-2 space-x-2 whitespace-nowrap">
                  {l.status === "pending" ? (
                    <>
                      <button
                        type="button"
                        className="text-emerald-700 text-xs font-semibold"
                        onClick={() => setStatus(l.id, "approved")}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="text-red-600 text-xs font-semibold"
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
                  No leave requests in this filter
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
