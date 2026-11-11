"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Letter = { id: number; subject: string; body: string; name: string; role: string; step: string };

export default function FacultyRequestsPage() {
  const [items, setItems] = useState<Letter[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Letter[] }>("/api/v1/requests/inbox").then((data) => setItems(data.items || [])).catch((e) => setErr(e.message));
  };

  useEffect(() => { load(); }, []);

  const decide = async (id: number, decision: string) => {
    setErr("");
    try {
      await apiFetch(`/api/v1/requests/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, note: "" }) });
      setMsg(decision === "approve" ? "Passed to the next office." : "Letter returned.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not decide");
    }
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Request desk</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b">A letter appears here only when the route has reached your office. An advisor sees their own students. A HoD sees their department. A dean sees the school step.</p>
        {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
        {msg ? <p className="px-4 py-2 text-sm text-emerald-700">{msg}</p> : null}
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">From</th><th>Letter</th><th>Office</th><th></th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.name}<div className="text-xs text-slate-500">{item.role}</div></td>
                <td className="px-3 py-2">{item.subject}<div className="text-xs text-slate-500">{item.body}</div></td>
                <td className="px-3 py-2">{item.step}</td>
                <td className="px-3 py-2 space-x-2">
                  <button type="button" className="underline" onClick={() => decide(item.id, "approve")}>Approve</button>
                  <button type="button" className="underline" onClick={() => decide(item.id, "reject")}>Return</button>
                </td>
              </tr>
            ))}
            {!items.length && !err ? <tr><td colSpan={4} className="px-3 py-4 text-slate-500">No letter is at this desk.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
