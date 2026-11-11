"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { SlipPaper } from "@/components/SlipPaper";
import { apiFetch } from "@/lib/api";

type Slip = { id: number; period: string; gross: number; deduction: number; net: number; note: string; status: string; number?: string };

export default function FacultyPayrollPage() {
  const [name, setName] = useState("");
  const [items, setItems] = useState<Slip[]>([]);
  const [open, setOpen] = useState<Slip | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ name?: string; items: Slip[] }>("/api/v1/finance/payroll")
      .then((data) => {
        setName(data.name || "");
        setItems(data.items || []);
      })
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Payslips</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b">Finance records the pay. Open a month to print the payslip.</p>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Period</th><th>Gross</th><th>Deduction</th><th>Net</th><th>Slip</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.period}</td>
                <td className="px-3 py-2">{item.gross}</td>
                <td className="px-3 py-2">{item.deduction}</td>
                <td className="px-3 py-2">{item.net}</td>
                <td className="px-3 py-2">
                  <button type="button" className="underline text-[#0B2A4A]" onClick={() => setOpen(item)}>Print</button>
                </td>
              </tr>
            ))}
            {!items.length && !err ? <tr><td colSpan={5} className="px-3 py-4 text-slate-500">No payslips yet.</td></tr> : null}
          </tbody>
        </table>
        <p className="px-4 py-3 text-sm"><Link className="text-[#0B2A4A] underline" href="/ack">All acknowledgement slips</Link></p>
      </section>
      {open ? (
        <section className="mt-4">
          <div className="mb-3 flex gap-2">
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => window.print()}>Print</button>
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setOpen(null)}>Close</button>
            {open.number ? <Link className="px-3 py-1.5 rounded border text-sm" href={`/ack/${open.number}`}>{open.number}</Link> : null}
          </div>
          <SlipPaper
            design={{
              institution: "Kalasalingam Academy of Research and Education",
              subtitle: "Office of the Finance Officer",
              document_title: "PAYSLIP",
              body: `Staff {{name}}\nPeriod {{title}}\nPayslip {{number}}\nStatus {{status}}`,
              footer: "This payslip is generated from the campus payroll record.",
              signatory: "Finance Officer",
              signatory_title: "Office of the Finance Officer",
              show_particulars: true,
              show_signatory: true,
            }}
            tokens={{ number: open.number || open.period, title: open.period, status: open.status, date: "", name, email: "" }}
            lines={[
              { label: "Gross pay", value: String(open.gross) },
              { label: "Deduction", value: String(open.deduction) },
              { label: "Net pay", value: String(open.net) },
              { label: "Note", value: open.note || "—" },
            ]}
          />
        </section>
      ) : null}
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
