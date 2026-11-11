"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Slip = { id: number; period: string; gross: number; deduction: number; net: number; note: string; status: string };

export default function FacultyPayrollPage() {
  const [items, setItems] = useState<Slip[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ items: Slip[] }>("/api/v1/finance/payroll")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Payroll</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b">Payslips recorded by finance. Open Acknowledgements for the printable slip.</p>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Period</th><th>Gross</th><th>Deduction</th><th>Net</th><th>Status</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.period}</td>
                <td className="px-3 py-2">{item.gross}</td>
                <td className="px-3 py-2">{item.deduction}</td>
                <td className="px-3 py-2">{item.net}</td>
                <td className="px-3 py-2">{item.status}</td>
              </tr>
            ))}
            {!items.length && !err ? <tr><td colSpan={5} className="px-3 py-4 text-slate-500">No payslips yet.</td></tr> : null}
          </tbody>
        </table>
        <p className="px-4 py-3 text-sm"><Link className="text-[#0B2A4A] underline" href="/ack">Open acknowledgement slips</Link></p>
      </section>
      <section className="uis-panel mt-4">
        <h2 className="uis-panel-title">Hall ticket recommendation</h2>
        <form
          className="p-4 grid md:grid-cols-4 gap-2 items-end"
          onSubmit={async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            setErr("");
            try {
              await apiFetch("/api/v1/hall-ticket/waivers", {
                method: "POST",
                body: JSON.stringify({
                  student_id: String(data.get("student_id") || ""),
                  reason: String(data.get("reason") || ""),
                  source: "faculty",
                  active: true,
                }),
              });
              form.reset();
              setErr("Hall ticket enabled for this student.");
            } catch (error) {
              setErr(error instanceof Error ? error.message : "Could not save the recommendation");
            }
          }}
        >
          <label className="text-xs text-slate-500">Register number
            <input name="student_id" required className="mt-1 w-full border rounded px-2 py-1 text-sm" />
          </label>
          <label className="text-xs text-slate-500 md:col-span-2">Reason
            <input name="reason" required className="mt-1 w-full border rounded px-2 py-1 text-sm" />
          </label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Enable hall ticket</button>
        </form>
      </section>
    </AppShell>
  );
}
