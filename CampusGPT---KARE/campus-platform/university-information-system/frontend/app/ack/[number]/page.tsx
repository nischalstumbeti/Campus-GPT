"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Slip = {
  number: string;
  title: string;
  summary: string;
  email: string;
  email_sent: boolean;
  created_at: string;
};

export default function AcknowledgementPage() {
  const params = useParams();
  const number = String(params.number || "");
  const [slip, setSlip] = useState<Slip | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!number) return;
    apiFetch<Slip>(`/api/v1/acknowledgements/${number}`)
      .then(setSlip)
      .catch((e) => setErr(e.message));
  }, [number]);

  return (
    <AppShell>
      <section className="uis-panel max-w-2xl">
        <h1 className="uis-panel-title">Acknowledgement slip</h1>
        <div className="p-4 space-y-3 text-sm">
          {err ? <p className="text-red-600">{err}</p> : null}
          {!slip && !err ? <p className="text-slate-500">Loading slip…</p> : null}
          {slip ? (
            <div className="border rounded-lg p-4 space-y-2 print:border-black">
              <p className="text-xs uppercase tracking-wide text-slate-500">KARE University Information System</p>
              <h2 className="text-lg font-bold text-[#0B2A4A]">{slip.title}</h2>
              <p className="font-mono text-base">{slip.number}</p>
              <p className="whitespace-pre-wrap text-slate-700">{slip.summary}</p>
              <p>Email: {slip.email || "—"} · {slip.email_sent ? "Sent" : "Not sent"}</p>
              <p className="text-slate-500">{slip.created_at.replace("T", " ").slice(0, 19)} UTC</p>
              <div className="flex gap-3 print:hidden">
                <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white" onClick={() => window.print()}>
                  Print slip
                </button>
                <Link href="/ack" className="px-3 py-1.5 rounded border">All slips</Link>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </AppShell>
  );
}
