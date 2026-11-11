"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Leave = { id: number; name: string; role: string; start_date: string; end_date: string; reason: string; status: string; decided_by: string };
type Slot = { day: string; start: string; end: string; code: string; course: string; room: string; section: string };

export default function PersonnelPage() {
  const [mine, setMine] = useState<Leave[]>([]);
  const [inbox, setInbox] = useState<Leave[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [form, setForm] = useState({ start_date: "", end_date: "", reason: "" });
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Leave[] }>("/api/v1/personnel/leave").then((data) => setMine(data.items || [])).catch((e) => setErr(e.message));
    apiFetch<{ items: Leave[] }>("/api/v1/personnel/leave/inbox").then((data) => setInbox(data.items || [])).catch(() => setInbox([]));
    apiFetch<{ slots: Slot[] }>("/api/v1/faculty/timetable").then((data) => setSlots(data.slots || [])).catch(() => setSlots([]));
  };

  useEffect(() => { load(); }, []);

  const apply = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      await apiFetch("/api/v1/personnel/leave", { method: "POST", body: JSON.stringify(form) });
      setMsg("Leave sent to the personnel desk.");
      setForm({ start_date: "", end_date: "", reason: "" });
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not apply");
    }
  };

  const decide = async (id: number, decision: string) => {
    await apiFetch(`/api/v1/personnel/leave/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, note: "" }) });
    load();
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Personnel</h1>
        <p className="px-4 pt-3 text-sm text-slate-600">Apply for your own leave here. A HoD decides faculty leave in the same department. A dean decides HoD leave. The director or an administrator can decide any leave except their own.</p>
        <form onSubmit={apply} className="p-4 grid md:grid-cols-4 gap-2 items-end">
          {err ? <p className="text-sm text-red-600 md:col-span-4">{err}</p> : null}
          {msg ? <p className="text-sm text-emerald-700 md:col-span-4">{msg}</p> : null}
          <label className="text-xs text-slate-500">From<input required type="date" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label>
          <label className="text-xs text-slate-500">To<input required type="date" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></label>
          <label className="text-xs text-slate-500">Reason<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Apply</button>
        </form>
        <table className="w-full text-sm">
          <tbody>
            {mine.map((item) => (
              <tr key={item.id} className="border-t"><td className="px-3 py-2">{item.start_date} to {item.end_date}</td><td>{item.reason}</td><td className="capitalize">{item.status}{item.decided_by ? ` · ${item.decided_by}` : ""}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="uis-panel mb-4">
        <h2 className="uis-panel-title">Leave waiting for you</h2>
        <table className="w-full text-sm">
          <tbody>
            {inbox.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.name} · {item.role}</td>
                <td>{item.start_date} to {item.end_date}</td>
                <td>{item.reason}</td>
                <td className="space-x-2">
                  <button type="button" className="underline" onClick={() => decide(item.id, "approve")}>Approve</button>
                  <button type="button" className="underline" onClick={() => decide(item.id, "reject")}>Return</button>
                </td>
              </tr>
            ))}
            {!inbox.length ? <tr><td className="px-3 py-4 text-slate-500">No staff leave is waiting.</td></tr> : null}
          </tbody>
        </table>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">Duty timetable</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Day</th><th>Time</th><th>Class</th><th>Room</th></tr></thead>
          <tbody>
            {slots.map((slot, index) => (
              <tr key={`${slot.day}-${slot.start}-${index}`} className="border-t">
                <td className="px-3 py-2">{slot.day}</td>
                <td>{slot.start}–{slot.end}</td>
                <td>{slot.code} {slot.course} {slot.section}</td>
                <td>{slot.room}</td>
              </tr>
            ))}
            {!slots.length ? <tr><td colSpan={4} className="px-3 py-4 text-slate-500">No class duty is on the timetable.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
