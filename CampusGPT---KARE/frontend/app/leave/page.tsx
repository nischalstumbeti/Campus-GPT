"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { apiGet, apiPost } from "@/lib/api";

type Leave = {
  id: number;
  from_date: string;
  to_date: string;
  reason: string;
  destination: string;
  status: string;
};

type Allocation = {
  hostel?: string;
  block?: string;
  room?: string;
  bed?: string | number;
  mess?: string;
  status?: string;
};

function LeaveInner() {
  const [rows, setRows] = useState<Leave[]>([]);
  const [allocation, setAllocation] = useState<Allocation | null>(null);
  const [source, setSource] = useState<string>("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [dest, setDest] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () =>
    apiGet<{ leaves: Leave[]; allocation?: Allocation | null; source?: string }>("/api/me/leaves")
      .then((d) => {
        setRows(d.leaves || []);
        setAllocation(d.allocation || null);
        setSource(d.source || "");
      })
      .catch(() => {
        setRows([]);
        setAllocation(null);
        setErr("Could not load leave requests.");
      });

  useEffect(() => {
    load();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg("");
    setErr("");
    if (from && to && to < from) {
      setErr("End date must be on or after start date.");
      return;
    }
    try {
      const res = await apiPost<{ message?: string; status?: string; source?: string }>("/api/me/leaves", {
        from_date: from,
        to_date: to,
        reason,
        destination: dest,
      });
      setFrom("");
      setTo("");
      setReason("");
      setDest("");
      setMsg(res.message || `Leave submitted. Status: ${res.status || "pending"}.`);
      if (res.source) setSource(res.source);
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not submit leave.");
    }
  };

  return (
    <CopilotShell title="Hostel">
      <div className="min-h-full bg-white relative">
        <main className="max-w-3xl mx-auto px-4 py-8 relative z-10">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <h1 className="text-2xl font-bold text-primary">Hostel leave</h1>
            <SyncBadge source={source} />
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Apply here — the request is stored in KARE UIS for the hostel warden and your faculty.
          </p>
          {allocation && (
            <div className="mb-6 rounded-xl border border-gray-100 bg-primary/5 px-4 py-3 text-sm text-gray-700">
              <p className="font-medium text-primary">Room (KARE UIS)</p>
              <p className="mt-1">
                {[allocation.hostel, allocation.block, allocation.room && `Room ${allocation.room}`, allocation.bed != null && `Bed ${allocation.bed}`, allocation.mess]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
          )}
          <form onSubmit={submit} className="grid gap-2 p-4 rounded-2xl border border-gray-100 bg-white mb-6">
            <label className="text-xs text-gray-500">From</label>
            <input required type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-xl border px-3 py-2" />
            <label className="text-xs text-gray-500">To</label>
            <input required type="date" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-xl border px-3 py-2" />
            <input required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" className="rounded-xl border px-3 py-2" />
            <input value={dest} onChange={(e) => setDest(e.target.value)} placeholder="Destination" className="rounded-xl border px-3 py-2" />
            <button className="px-4 py-2 rounded-xl bg-primary text-white font-medium w-fit">Submit leave</button>
            {msg && <p className="text-sm text-green-700">{msg}</p>}
            {err && <p className="text-sm text-red-600">{err}</p>}
          </form>
          <div className="space-y-3">
            {rows.map((r) => (
              <div key={r.id} className="p-4 rounded-2xl border border-gray-100 bg-white">
                <div className="flex justify-between">
                  <p className="font-medium text-primary">
                    {r.from_date} → {r.to_date}
                  </p>
                  <span
                    className={`text-xs capitalize ${
                      r.status === "approved" ? "text-green-700" : r.status === "rejected" ? "text-red-600" : "text-amber-700"
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                <p className="text-sm text-gray-600">{r.reason}</p>
                {r.destination && <p className="text-xs text-gray-500">{r.destination}</p>}
              </div>
            ))}
            {!rows.length && (
              <p className="text-sm text-gray-400 rounded-2xl border border-dashed border-gray-200 p-6 text-center">
                No leave requests yet. Submit above — or ask Campus-GPT “Apply for hostel leave” and confirm.
              </p>
            )}
          </div>
        </main>
      </div>
    </CopilotShell>
  );
}

export default function LeavePage() {
  return (
    <RequireAuth roles={["student"]}>
      <LeaveInner />
    </RequireAuth>
  );
}
