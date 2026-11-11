"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Route = { id: number; name: string; steps: string[]; active: boolean };
type Letter = { id: number; subject: string; body: string; name: string; step: string; status: string };

export default function AdminRequestsPage() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [inbox, setInbox] = useState<Letter[]>([]);
  const [name, setName] = useState("Bonafide");
  const [steps, setSteps] = useState("advisor,hod,school_dean");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Route[] }>("/api/v1/admin/request-routes").then((data) => setRoutes(data.items || [])).catch((e) => setErr(e.message));
    apiFetch<{ items: Letter[] }>("/api/v1/requests/inbox").then((data) => setInbox(data.items || [])).catch(() => setInbox([]));
  };

  useEffect(() => { load(); }, []);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      await apiFetch("/api/v1/admin/request-routes", { method: "POST", body: JSON.stringify({ name, steps, active: true }) });
      setMsg("Route saved. Students can choose it when they write a letter.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not save the route");
    }
  };

  const decide = async (id: number, decision: string) => {
    await apiFetch(`/api/v1/requests/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, note: "" }) });
    setMsg(decision === "approve" ? "Passed to the next office." : "Letter returned.");
    load();
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Request routes</h1>
        <p className="px-4 pt-3 text-sm text-slate-600">A student letter moves through these offices in order. Use advisor, hod, school_dean, director, coe, or admin, separated by commas.</p>
        <form onSubmit={save} className="p-4 grid md:grid-cols-3 gap-2 items-end">
          {err ? <p className="text-sm text-red-600 md:col-span-3">{err}</p> : null}
          {msg ? <p className="text-sm text-emerald-700 md:col-span-3">{msg}</p> : null}
          <label className="text-xs text-slate-500">Name<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="text-xs text-slate-500">Offices<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={steps} onChange={(e) => setSteps(e.target.value)} /></label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Save route</button>
        </form>
        <ul className="px-4 pb-4 text-sm">
          {routes.map((route) => <li key={route.id} className="border-t py-2">{route.name}: {route.steps.join(" → ")}{route.active ? "" : " (closed)"}</li>)}
        </ul>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">Waiting at your desk</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">From</th><th>Subject</th><th></th></tr></thead>
          <tbody>
            {inbox.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.name}</td>
                <td className="px-3 py-2">{item.subject}<div className="text-xs text-slate-500">{item.body}</div></td>
                <td className="px-3 py-2 space-x-2">
                  <button type="button" className="underline" onClick={() => decide(item.id, "approve")}>Approve</button>
                  <button type="button" className="underline" onClick={() => decide(item.id, "reject")}>Return</button>
                </td>
              </tr>
            ))}
            {!inbox.length ? <tr><td colSpan={3} className="px-3 py-4 text-slate-500">Nothing is waiting for this login.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
