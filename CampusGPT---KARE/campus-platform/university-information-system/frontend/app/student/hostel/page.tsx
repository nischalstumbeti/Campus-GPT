"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

export default function HostelPage() {
  const [data, setData] = useState<any>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [dest, setDest] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => apiFetch("/api/v1/student/hostel").then(setData).catch(() => setData(null));
  useEffect(() => {
    load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      await apiFetch("/api/v1/student/hostel/leave", {
        method: "POST",
        body: JSON.stringify({
          from_date: from,
          to_date: to,
          reason,
          destination: dest,
        }),
      });
      setFrom("");
      setTo("");
      setReason("");
      setDest("");
      setMsg("Leave submitted. Pending hostel warden approval — also visible in Campus-GPT and to your faculty.");
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not submit leave");
    }
  };

  const a = data?.allocation;
  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-4">Hostel</h1>
      {a ? (
        <div className="bg-white border rounded-lg p-4 mb-4 text-sm space-y-1">
          <p>
            <span className="text-slate-500">Hostel:</span> {a.hostel}
          </p>
          <p>
            <span className="text-slate-500">Block / Room:</span> {a.block} · {a.room} (Bed {a.bed})
          </p>
          <p>
            <span className="text-slate-500">Status:</span> {a.status}
          </p>
        </div>
      ) : (
        <p className="text-sm text-slate-500 mb-4">No allocation</p>
      )}

      <form onSubmit={submit} className="bg-white border rounded-lg p-4 mb-6 grid gap-2 max-w-xl">
        <h2 className="text-sm font-semibold">Apply for leave</h2>
        <label className="text-xs text-slate-500">From</label>
        <input required type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="border rounded-lg px-3 py-2 text-sm" />
        <label className="text-xs text-slate-500">To</label>
        <input required type="date" value={to} onChange={(e) => setTo(e.target.value)} className="border rounded-lg px-3 py-2 text-sm" />
        <input required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" className="border rounded-lg px-3 py-2 text-sm" />
        <input value={dest} onChange={(e) => setDest(e.target.value)} placeholder="Destination" className="border rounded-lg px-3 py-2 text-sm" />
        <button type="submit" className="w-fit bg-brand text-white rounded-lg px-4 py-2 text-sm font-medium">
          Submit leave
        </button>
        {err && <p className="text-sm text-red-700">{err}</p>}
        {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      </form>

      <h2 className="text-sm font-semibold mb-2">Leave requests</h2>
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">From</th>
              <th className="px-3 py-2">To</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(data?.leaves || []).map((l: any) => (
              <tr key={l.id || `${l.from}-${l.to}`} className="border-t">
                <td className="px-3 py-2">{l.from}</td>
                <td className="px-3 py-2">{l.to}</td>
                <td className="px-3 py-2">
                  {l.reason}
                  {l.destination ? <span className="block text-xs text-slate-500">{l.destination}</span> : null}
                </td>
                <td className="px-3 py-2 capitalize text-xs">{l.source || "uis"}</td>
                <td className="px-3 py-2 capitalize">{l.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
