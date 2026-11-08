"use client";

import { FormEvent, useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { apiGet, apiPost } from "@/lib/api";

type Payment = {
  id: number;
  amount: number;
  method: string;
  note: string;
  receipt_no?: string;
  created_at?: string;
};

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
  student_email: string;
  fee_title: string;
  amount_paid: number;
  total_amount: number;
  paid_amount: number;
  remaining: number;
  method: string;
  paid_at: string;
  status: string;
};

function FeesInner() {
  const [fees, setFees] = useState<Fee[]>([]);
  const [reminders, setReminders] = useState<{ id: number; message: string }[]>([]);
  const [category, setCategory] = useState("");
  const [payAmount, setPayAmount] = useState<Record<number, string>>({});
  const [editing, setEditing] = useState<Record<number, boolean>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [payBusy, setPayBusy] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [source, setSource] = useState("");

  const load = () =>
    apiGet<{ fees: Fee[]; reminders: { id: number; message: string }[]; category: string; source?: string }>("/api/fees/mine")
      .then((d) => {
        setFees(d.fees || []);
        setReminders(d.reminders || []);
        setCategory(d.category || "");
        setSource(d.source || "");
      })
      .catch(() => setFees([]));

  useEffect(() => {
    load();
  }, []);

  const pay = async (e: FormEvent, fee: Fee) => {
    e.preventDefault();
    if (payBusy) return;
    setMsg("");
    setErr("");
    const amount = Number(payAmount[fee.id] || 0);
    if (!amount || amount <= 0) {
      setErr("Enter a valid amount to pay.");
      return;
    }
    setPayBusy(true);
    try {
      const res = await apiPost<{ fee: Fee; receipt: Receipt; message: string }>(`/api/fees/mine/${fee.id}/pay`, {
        amount,
        method: "demo_upi",
        note: "Student portal demo payment",
      });
      setPayAmount((p) => ({ ...p, [fee.id]: "" }));
      setEditing((p) => ({ ...p, [fee.id]: false }));
      setReceipt(res.receipt);
      setMsg(res.message || "Payment recorded.");
      load();
    } catch {
      setErr("Payment failed. Check the amount and try again.");
    } finally {
      setPayBusy(false);
    }
  };

  return (
    <CopilotShell title="Fees">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h1 className="text-2xl font-bold text-primary">Pay fees</h1>
          <SyncBadge source={source} />
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Same fee records as KARE UIS. Enter an amount and pay. Your category:{" "}
          <span className="font-medium capitalize">{category?.replace("_", " ") || "—"}</span>
        </p>
        {err && <p className="text-sm text-red-700 mb-3">{err}</p>}
        {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}

        {reminders.length > 0 && (
          <div className="mb-6 space-y-2">
            {reminders.slice(0, 3).map((r) => (
              <div key={r.id} className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {r.message}
              </div>
            ))}
          </div>
        )}

        <div className="space-y-4">
          {fees.map((f) => (
            <div key={f.id} className="rounded-2xl border border-gray-100 bg-white p-4">
              <div className="flex flex-wrap justify-between gap-2 mb-3">
                <div>
                  <p className="font-semibold text-primary">{f.title}</p>
                  <p className="text-xs text-gray-500 capitalize">
                    {f.category.replace("_", " ")} · deadline {f.deadline || "—"} · {f.status}
                  </p>
                </div>
                <div className="text-right text-sm tabular-nums">
                  <p className="text-gray-600">Total ₹{Number(f.total_amount).toLocaleString("en-IN")}</p>
                  <p className="text-emerald-700 font-medium">Paid ₹{Number(f.paid_amount).toLocaleString("en-IN")}</p>
                  <p className="text-amber-700 font-semibold">
                    Remaining ₹{Number(f.remaining).toLocaleString("en-IN")}
                  </p>
                </div>
              </div>

              {f.remaining > 0 && (
                <div className="border-t border-gray-50 pt-3">
                  {!editing[f.id] ? (
                    <button
                      type="button"
                      onClick={() => {
                        setEditing((p) => ({ ...p, [f.id]: true }));
                        setPayAmount((p) => ({ ...p, [f.id]: String(f.remaining) }));
                      }}
                      className="px-4 py-2 rounded-xl bg-primary text-white text-sm font-medium"
                    >
                      Pay fee
                    </button>
                  ) : (
                    <form onSubmit={(e) => pay(e, f)} className="flex flex-wrap gap-2 items-end">
                      <label className="text-xs text-gray-500">
                        Amount to pay (₹)
                        <input
                          required
                          type="number"
                          min={1}
                          step="0.01"
                          max={f.remaining}
                          value={payAmount[f.id] || ""}
                          onChange={(e) => setPayAmount((p) => ({ ...p, [f.id]: e.target.value }))}
                          className="mt-1 block w-40 border rounded-xl px-3 py-2 text-sm"
                        />
                      </label>
                      <button
                        type="submit"
                        disabled={payBusy}
                        className="px-4 py-2 rounded-xl bg-primary text-white text-sm font-medium disabled:opacity-50"
                      >
                        Confirm pay
                      </button>
                      <button
                        type="button"
                        className="text-xs text-gray-500 underline"
                        onClick={() => setEditing((p) => ({ ...p, [f.id]: false }))}
                      >
                        Cancel
                      </button>
                    </form>
                  )}
                </div>
              )}

              {f.status === "paid" && (
                <p className="text-sm text-emerald-700 mt-2">Fully paid. Thank you.</p>
              )}

              {f.payments?.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-gray-500 mb-2">Payment history</p>
                  <ul className="space-y-1.5">
                    {[...f.payments].reverse().map((p) => (
                      <li
                        key={p.id}
                        className="flex flex-wrap justify-between gap-2 text-xs text-gray-600 rounded-lg bg-gray-50 px-3 py-2"
                      >
                        <span>
                          ₹{p.amount} · {p.method}
                          {p.receipt_no ? ` · ${p.receipt_no}` : ""}
                        </span>
                        <span>{p.created_at?.slice(0, 10)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
          {!fees.length && (
            <div className="rounded-2xl border border-dashed border-gray-200 p-8 text-center">
              <p className="text-sm text-gray-600 font-medium">No fee dues yet</p>
              <p className="text-xs text-gray-400 mt-2">
                Ask admin/faculty to publish a fee plan for your category (hostel / day scholar / bus) in Fee deadlines.
              </p>
            </div>
          )}
        </div>
      </div>

      {receipt && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setReceipt(null)}>
          <div
            id="fee-receipt-print"
            className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-xs uppercase tracking-wide text-primary font-semibold">Payment receipt</p>
            <h2 className="text-lg font-bold text-gray-900 mt-1">KARE · Campus-GPT</h2>
            <p className="text-sm text-gray-500 mt-1">Receipt no. {receipt.receipt_no}</p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Student</dt>
                <dd className="font-medium text-right">{receipt.student_name}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Fee</dt>
                <dd className="font-medium text-right">{receipt.fee_title}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Amount paid</dt>
                <dd className="font-semibold text-emerald-700">₹{receipt.amount_paid}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Total paid so far</dt>
                <dd>₹{receipt.paid_amount}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Remaining</dt>
                <dd className="font-semibold text-amber-700">₹{receipt.remaining}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Method</dt>
                <dd>{receipt.method}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-gray-500">Date</dt>
                <dd>{receipt.paid_at?.slice(0, 19).replace("T", " ")}</dd>
              </div>
            </dl>
            <p className="text-[11px] text-gray-400 mt-4">Demo UPI receipt · balances updated in the linked system of record</p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="flex-1 py-2.5 rounded-xl border text-sm font-medium"
                onClick={() => window.print()}
              >
                Download / Print PDF
              </button>
              <button
                type="button"
                className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-medium"
                onClick={() => setReceipt(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </CopilotShell>
  );
}

export default function FeesPage() {
  return (
    <RequireAuth roles={["student"]}>
      <FeesInner />
    </RequireAuth>
  );
}
