"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Item = {
  source: "exam" | "registration";
  id: number;
  kind: string;
  student_id: string;
  name: string;
  detail: string;
  status: string;
  advisor_status: string;
  hod_status: string;
  can_advise: boolean;
  can_hod: boolean;
};

const LABELS: Record<string, string> = {
  registration: "Course registration",
  withdrawal: "Course withdrawal",
  revaluation: "Revaluation",
  arrear: "Arrear",
  backlog: "Backlog",
};

export default function ApprovalsPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Item[] }>("/api/v1/faculty/approvals")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  const decide = async (item: Item, decision: "approved" | "rejected") => {
    setErr("");
    setMsg("");
    try {
      await apiFetch(`/api/v1/faculty/approvals/${item.source}/${item.id}`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      setMsg(`${LABELS[item.kind] || item.kind} ${decision}.`);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update");
    }
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Approvals</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">
          The faculty advisor approves first. The Head of Department approves next. The acknowledgement slip is issued after both approvals.
        </p>
        {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
        {msg ? <p className="px-4 py-2 text-sm text-emerald-700">{msg}</p> : null}
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Service</th>
              <th className="px-3 py-2">Courses</th>
              <th className="px-3 py-2">Advisor</th>
              <th className="px-3 py-2">HoD</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const advisorOpen = item.can_advise && item.advisor_status === "pending" && item.status !== "rejected";
              const hodOpen = item.can_hod && item.advisor_status === "approved" && item.hod_status === "pending";
              return (
                <tr key={`${item.source}-${item.id}`} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <p className="font-medium">{item.name}</p>
                    <p className="text-xs text-slate-500">{item.student_id}</p>
                  </td>
                  <td className="px-3 py-2">{LABELS[item.kind] || item.kind}</td>
                  <td className="px-3 py-2">{item.detail}</td>
                  <td className="px-3 py-2 capitalize">{item.advisor_status}</td>
                  <td className="px-3 py-2 capitalize">{item.hod_status}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {advisorOpen || hodOpen ? (
                      <>
                        <button type="button" className="text-emerald-700 font-medium mr-2" onClick={() => decide(item, "approved")}>
                          Approve
                        </button>
                        <button type="button" className="text-red-600 font-medium" onClick={() => decide(item, "rejected")}>
                          Reject
                        </button>
                      </>
                    ) : (
                      <span className="text-slate-400 capitalize">{item.status.replaceAll("_", " ")}</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {!items.length && !err ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-slate-500">
                  No requests are waiting.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
