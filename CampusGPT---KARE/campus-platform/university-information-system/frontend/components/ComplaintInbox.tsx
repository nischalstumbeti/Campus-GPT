"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Complaint = {
  id: number;
  student_id: string;
  student_name: string;
  section: string;
  category: string;
  audience: string;
  subject: string;
  description: string;
  status: string;
  resolution_note: string;
  resolver_username?: string | null;
  resolver_role?: string | null;
};

export default function ComplaintInbox({
  title,
  subtitle,
  defaultFilter = "open",
}: {
  title: string;
  subtitle: string;
  defaultFilter?: string;
}) {
  const [rows, setRows] = useState<Complaint[]>([]);
  const [filter, setFilter] = useState(defaultFilter);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = (status: string) => {
    const q = status === "all" ? "" : `?status=${status === "active" ? "open" : status}`;
    // For "active", fetch open + in_progress separately and merge
    if (status === "active") {
      Promise.all([
        apiFetch<{ complaints: Complaint[] }>("/api/v1/complaints?status=open"),
        apiFetch<{ complaints: Complaint[] }>("/api/v1/complaints?status=in_progress"),
      ])
        .then(([a, b]) => setRows([...(a.complaints || []), ...(b.complaints || [])]))
        .catch(() => setRows([]));
      return;
    }
    apiFetch<{ complaints: Complaint[] }>(`/api/v1/complaints${q}`)
      .then((d) => setRows(d.complaints || []))
      .catch(() => setRows([]));
  };

  useEffect(() => {
    load(filter);
  }, [filter]);

  const setStatus = async (id: number, status: string) => {
    setMsg("");
    setErr("");
    try {
      await apiFetch(`/api/v1/complaints/${id}/status`, {
        method: "POST",
        body: JSON.stringify({
          status,
          resolution_note: notes[id] || "",
        }),
      });
      setMsg(`Complaint #${id} marked ${status.replace("_", " ")}.`);
      load(filter);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#0B2A4A]">{title}</h1>
          <p className="text-sm text-slate-500">{subtitle}</p>
        </div>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="active">Open + in progress</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
          <option value="all">All</option>
        </select>
      </div>
      {err && <p className="text-sm text-red-700 mb-3">{err}</p>}
      {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}
      <div className="space-y-3">
        {rows.map((c) => (
          <div key={c.id} className="bg-white border rounded-xl p-4 shadow-sm text-sm">
            <div className="flex flex-wrap justify-between gap-2 mb-1">
              <div>
                <p className="font-medium text-[#0B2A4A]">{c.subject}</p>
                <p className="text-xs text-slate-500">
                  {c.student_name} · {c.student_id} · Sec {c.section}
                </p>
              </div>
              <span className="capitalize text-xs font-medium text-amber-700">
                {c.status.replace("_", " ")} · {c.category}
              </span>
            </div>
            {c.description && <p className="text-slate-600 mb-2">{c.description}</p>}
            <p className="text-[11px] text-slate-400 mb-2 capitalize">Routed to: {c.audience}</p>
            {(c.status === "open" || c.status === "in_progress") && (
              <div className="grid gap-2 max-w-xl">
                <input
                  value={notes[c.id] || ""}
                  onChange={(e) => setNotes((prev) => ({ ...prev, [c.id]: e.target.value }))}
                  placeholder="Resolution / update note"
                  className="border rounded-lg px-3 py-2 text-sm"
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="text-xs font-semibold text-blue-700"
                    onClick={() => setStatus(c.id, "in_progress")}
                  >
                    Mark in progress
                  </button>
                  <button
                    type="button"
                    className="text-xs font-semibold text-emerald-700"
                    onClick={() => setStatus(c.id, "resolved")}
                  >
                    Resolve
                  </button>
                  <button
                    type="button"
                    className="text-xs font-semibold text-slate-600"
                    onClick={() => setStatus(c.id, "closed")}
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
            {c.resolution_note && (
              <p className="text-xs bg-slate-50 border rounded-lg px-3 py-2 mt-2">
                Note: {c.resolution_note}
                {c.resolver_username ? ` — ${c.resolver_username}` : ""}
              </p>
            )}
          </div>
        ))}
        {!rows.length && <p className="text-sm text-slate-400">No complaints in this filter</p>}
      </div>
    </div>
  );
}
