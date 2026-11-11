"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Route = { id: number; name: string; steps: string[] };
type Letter = { id: number; subject: string; status: string; step: string; steps: string[]; route: string; note: string };

export default function StudentRequestsPage() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [items, setItems] = useState<Letter[]>([]);
  const [routeId, setRouteId] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    apiFetch<{ items: Route[] }>("/api/v1/requests/routes").then((data) => {
      setRoutes(data.items || []);
      setRouteId(data.items?.[0] ? String(data.items[0].id) : "");
    }).catch((e) => setErr(e.message));
    apiFetch<{ items: Letter[] }>("/api/v1/requests/mine").then((data) => setItems(data.items || [])).catch((e) => setErr(e.message));
  };

  useEffect(() => { load(); }, []);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      await apiFetch("/api/v1/requests", { method: "POST", body: JSON.stringify({ route_id: Number(routeId), subject, body }) });
      setSubject("");
      setBody("");
      setMsg("Letter sent. It waits at the first office on the route.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not send the letter");
    }
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Requisition letter</h1>
        <form onSubmit={send} className="p-4 space-y-2">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-emerald-700">{msg}</p> : null}
          <label className="block text-xs text-slate-500">Route
            <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={routeId} onChange={(e) => setRouteId(e.target.value)}>
              {routes.map((route) => <option key={route.id} value={route.id}>{route.name} · {route.steps.join(" → ")}</option>)}
            </select>
          </label>
          <label className="block text-xs text-slate-500">Subject
            <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label className="block text-xs text-slate-500">Letter
            <textarea required rows={5} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={body} onChange={(e) => setBody(e.target.value)} />
          </label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" disabled={!routeId}>Submit</button>
        </form>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">My letters</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Subject</th><th>Route</th><th>Now with</th><th>Status</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.subject}</td>
                <td className="px-3 py-2">{item.steps.join(" → ")}</td>
                <td className="px-3 py-2">{item.step || "—"}</td>
                <td className="px-3 py-2 capitalize">{item.status}{item.note ? ` · ${item.note}` : ""}</td>
              </tr>
            ))}
            {!items.length ? <tr><td colSpan={4} className="px-3 py-4 text-slate-500">No letters yet.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
