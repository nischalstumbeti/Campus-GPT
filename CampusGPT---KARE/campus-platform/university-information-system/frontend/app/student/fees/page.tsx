"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Payment = { id: number; amount: number; method: string; receipt_no?: string; created_at?: string };
type Fee = {
  id: number;
  title: string;
  category: string;
  total_amount: number;
  paid_amount: number;
  remaining: number;
  deadline: string;
  status: string;
  payments: Payment[];
};
type Receipt = {
  receipt_no: string;
  student_name: string;
  fee_title: string;
  amount_paid: number;
  paid_amount: number;
  remaining: number;
  method: string;
  paid_at: string;
};

export default function StudentFeesPage() {
  const [fees, setFees] = useState<Fee[]>([]);
  const [reminders, setReminders] = useState<{ id: number; message: string }[]>([]);
  const [category, setCategory] = useState("");
  const [payAmount, setPayAmount] = useState<Record<number, string>>({});
  const [editing, setEditing] = useState<Record<number, boolean>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [payBusy, setPayBusy] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [slip, setSlip] = useState("");
  const [method, setMethod] = useState("UPI");
  const [gateway, setGateway] = useState<{ provider: string; merchant_name: string } | null>(null);

  const load = () =>
    apiFetch<{ fees: Fee[]; reminders: { id: number; message: string }[]; category: string }>("/api/v1/fees/mine")
      .then((d) => {
        setFees(d.fees || []);
        setReminders(d.reminders || []);
        setCategory(d.category || "");
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load fees"));

  useEffect(() => {
    load();
    apiFetch<{ provider: string; merchant_name: string }>("/api/v1/finance/gateway")
      .then(setGateway)
      .catch(() => setGateway(null));
  }, []);

  const pay = async (e: FormEvent, fee: Fee) => {
    e.preventDefault();
    if (payBusy) return;
    setMsg("");
    setErr("");
    const amount = Number(payAmount[fee.id] || 0);
    if (!amount) return;
    setPayBusy(true);
    try {
      const res = await apiFetch<{ receipt: Receipt; message: string; acknowledgement?: { number: string; link: string } }>(`/api/v1/fees/mine/${fee.id}/pay`, {
        method: "POST",
        body: JSON.stringify({ amount, method, note: `Collected on ${gateway?.merchant_name || "the institute gateway"}` }),
      });
      setReceipt(res.receipt);
      setSlip(res.acknowledgement?.number || "");
      setMsg(res.message);
      setEditing((p) => ({ ...p, [fee.id]: false }));
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Payment failed");
    } finally {
      setPayBusy(false);
    }
  };

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand mb-1">Pay fees</h1>
      <p className="text-sm text-slate-600 mb-4">
        Payments are collected by {gateway?.merchant_name || "the institute gateway"}
        {gateway?.provider ? ` (${gateway.provider})` : ""}. Category:{" "}
        <span className="font-medium capitalize">{category.replace("_", " ") || "—"}</span>
      </p>
      {err && <p className="text-sm text-red-700 mb-3">{err}</p>}
      {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}
      {reminders.slice(0, 3).map((r) => (
        <div key={r.id} className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {r.message}
        </div>
      ))}
      <div className="space-y-3 mt-4">
        {fees.map((f) => (
          <div key={f.id} className="bg-white border border-slate-200 rounded-lg p-4">
            <div className="flex flex-wrap justify-between gap-2">
              <div>
                <p className="font-semibold text-brand">{f.title}</p>
                <p className="text-xs text-slate-500 capitalize">
                  {f.category.replace("_", " ")} · deadline {f.deadline || "—"} · {f.status}
                </p>
              </div>
              <div className="text-right text-sm tabular-nums">
                <p>Total ₹{f.total_amount}</p>
                <p className="text-emerald-700 font-medium">Paid ₹{f.paid_amount}</p>
                <p className="text-amber-700 font-semibold">Remaining ₹{f.remaining}</p>
              </div>
            </div>
            {f.remaining > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-100">
                {!editing[f.id] ? (
                  <button
                    type="button"
                    className="px-4 py-2 rounded-md bg-brand text-white text-sm"
                    onClick={() => {
                      setEditing((p) => ({ ...p, [f.id]: true }));
                      setPayAmount((p) => ({ ...p, [f.id]: String(f.remaining) }));
                    }}
                  >
                    Pay fee
                  </button>
                ) : (
                  <form onSubmit={(e) => pay(e, f)} className="flex flex-wrap gap-2 items-end">
                    <label className="text-xs text-slate-500">
                      Amount (₹)
                      <input
                        type="number"
                        min={1}
                        max={f.remaining}
                        step="0.01"
                        className="mt-1 block border rounded-md px-3 py-2 text-sm"
                        value={payAmount[f.id] || ""}
                        onChange={(e) => setPayAmount((p) => ({ ...p, [f.id]: e.target.value }))}
                      />
                    </label>
                    <label className="text-xs text-slate-500">
                      Pay using
                      <select className="mt-1 block border rounded-md px-3 py-2 text-sm" value={method} onChange={(e) => setMethod(e.target.value)}>
                        <option>UPI</option>
                        <option>Card</option>
                        <option>Net banking</option>
                        <option>Cash at counter</option>
                      </select>
                    </label>
                    <button
                      type="submit"
                      disabled={payBusy}
                      className="px-4 py-2 rounded-md bg-brand text-white text-sm disabled:opacity-50"
                    >
                      Confirm pay
                    </button>
                    <button type="button" className="text-xs underline" onClick={() => setEditing((p) => ({ ...p, [f.id]: false }))}>
                      Cancel
                    </button>
                  </form>
                )}
              </div>
            )}
            {f.payments?.length > 0 && (
              <ul className="mt-3 text-xs text-slate-500 space-y-1">
                {[...f.payments].reverse().map((p) => (
                  <li key={p.id}>
                    ₹{p.amount} · {p.receipt_no || p.method} · {p.created_at?.slice(0, 10)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {!fees.length && <p className="text-sm text-slate-400">No fees published yet.</p>}
      </div>

      {receipt && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setReceipt(null)}>
          <div className="bg-white rounded-lg max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <p className="text-xs uppercase text-brand font-semibold">Payment receipt · UIS</p>
            <p className="font-bold mt-1">{receipt.receipt_no}</p>
            <dl className="mt-3 text-sm space-y-1">
              <div className="flex justify-between"><dt>Student</dt><dd>{receipt.student_name}</dd></div>
              <div className="flex justify-between"><dt>Fee</dt><dd>{receipt.fee_title}</dd></div>
              <div className="flex justify-between"><dt>Paid now</dt><dd className="text-emerald-700 font-semibold">₹{receipt.amount_paid}</dd></div>
              <div className="flex justify-between"><dt>Total paid</dt><dd>₹{receipt.paid_amount}</dd></div>
              <div className="flex justify-between"><dt>Remaining</dt><dd className="text-amber-700 font-semibold">₹{receipt.remaining}</dd></div>
            </dl>
            {slip ? (
              <p className="mt-3 text-sm">
                Slip <Link className="underline text-[#0B2A4A]" href={`/ack/${slip}`}>{slip}</Link>
              </p>
            ) : null}
            <button type="button" className="mt-4 w-full py-2 bg-brand text-white rounded-md text-sm" onClick={() => setReceipt(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
