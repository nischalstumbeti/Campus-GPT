"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Gateway = { provider: string; merchant_name: string; key_id: string; secret_saved: boolean; live_charges: boolean };
type Tx = { id: number; receipt_no: string; amount: number; method: string; title: string; payer: string; created_at: string };

export default function FinancePage() {
  const [gateway, setGateway] = useState<Gateway | null>(null);
  const [secret, setSecret] = useState("");
  const [rows, setRows] = useState<Tx[]>([]);
  const [pay, setPay] = useState({ username: "", period: "", gross: "", deduction: "0", note: "" });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    apiFetch<Gateway>("/api/v1/finance/gateway").then(setGateway).catch((e) => setErr(e.message));
    apiFetch<{ items: Tx[] }>("/api/v1/admin/finance/transactions").then((data) => setRows(data.items || [])).catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  const saveGateway = async (e: FormEvent) => {
    e.preventDefault();
    if (!gateway) return;
    setErr("");
    try {
      const saved = await apiFetch<Gateway>("/api/v1/admin/finance/gateway", {
        method: "PUT",
        body: JSON.stringify({ ...gateway, key_secret: secret }),
      });
      setGateway(saved);
      setSecret("");
      setMsg("Payment gateway saved. Own gateway collects into the institute register. Live charges stay off until you turn them on.");
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not save the gateway");
    }
  };

  const savePayroll = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      const result = await apiFetch<{ acknowledgement?: { number: string }; net: number }>("/api/v1/admin/finance/payroll", {
        method: "POST",
        body: JSON.stringify({ ...pay, gross: Number(pay.gross), deduction: Number(pay.deduction) }),
      });
      setMsg(`Payslip recorded. Net ${result.net}. Slip ${result.acknowledgement?.number || ""}.`);
      setPay({ username: "", period: "", gross: "", deduction: "0", note: "" });
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not record payroll");
    }
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Finance</h1>
        <div className="p-4 space-y-3">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-brand">{msg}</p> : null}
          {gateway ? (
            <form onSubmit={saveGateway} className="grid md:grid-cols-3 gap-2 items-end">
              <label className="text-xs text-slate-500">Gateway
                <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={gateway.provider} onChange={(e) => setGateway({ ...gateway, provider: e.target.value })}>
                  <option value="own">Own institute gateway</option>
                  <option value="razorpay">Razorpay</option>
                  <option value="cashfree">Cashfree</option>
                  <option value="billdesk">BillDesk</option>
                  <option value="none">None</option>
                </select>
              </label>
              <label className="text-xs text-slate-500">Merchant name
                <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={gateway.merchant_name} onChange={(e) => setGateway({ ...gateway, merchant_name: e.target.value })} />
              </label>
              <label className="text-xs text-slate-500">Key id
                <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={gateway.key_id} onChange={(e) => setGateway({ ...gateway, key_id: e.target.value })} />
              </label>
              <label className="text-xs text-slate-500">Key secret
                <input type="password" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={secret} placeholder={gateway.secret_saved ? "Saved. Type to replace." : ""} onChange={(e) => setSecret(e.target.value)} />
              </label>
              <label className="text-sm flex items-center gap-2">
                <input type="checkbox" checked={gateway.live_charges} onChange={(e) => setGateway({ ...gateway, live_charges: e.target.checked })} />
                Live charges
              </label>
              <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Save gateway</button>
            </form>
          ) : null}
          <p className="text-xs text-slate-500">While live charges are off, student payments are collected on the institute ledger and a receipt slip is issued. Razorpay, Cashfree, or BillDesk keys can be stored here for a later live switch.</p>
        </div>
      </section>
      <section className="uis-panel mb-4">
        <h2 className="uis-panel-title">Payroll</h2>
        <form onSubmit={savePayroll} className="p-4 grid md:grid-cols-5 gap-2 items-end">
          <label className="text-xs text-slate-500">Username<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={pay.username} onChange={(e) => setPay({ ...pay, username: e.target.value })} /></label>
          <label className="text-xs text-slate-500">Period<input required placeholder="2026-11" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={pay.period} onChange={(e) => setPay({ ...pay, period: e.target.value })} /></label>
          <label className="text-xs text-slate-500">Gross<input required type="number" min={0} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={pay.gross} onChange={(e) => setPay({ ...pay, gross: e.target.value })} /></label>
          <label className="text-xs text-slate-500">Deduction<input type="number" min={0} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={pay.deduction} onChange={(e) => setPay({ ...pay, deduction: e.target.value })} /></label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Record payslip</button>
        </form>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">Fee register</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Receipt</th><th>Payer</th><th>Fee</th><th>Amount</th><th>Method</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t">
                <td className="px-3 py-2">{row.receipt_no}</td>
                <td className="px-3 py-2">{row.payer}</td>
                <td className="px-3 py-2">{row.title}</td>
                <td className="px-3 py-2">{row.amount}</td>
                <td className="px-3 py-2">{row.method}</td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={5} className="px-3 py-4 text-slate-500">No payments recorded.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
