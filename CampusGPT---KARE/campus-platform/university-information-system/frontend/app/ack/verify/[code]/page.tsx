"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API } from "@/lib/api";

type Check = { valid: boolean; number: string; title: string; status: string; issued_at: string };

export default function VerifyAcknowledgementPage() {
  const params = useParams();
  const code = String(params.code || "");
  const [row, setRow] = useState<Check | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!code) return;
    fetch(`${API}/api/v1/acknowledgements/verify/${encodeURIComponent(code)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((body as { detail?: string }).detail || "This code does not match an issued acknowledgement");
        setRow(body as Check);
      })
      .catch((error) => setErr(error instanceof Error ? error.message : "Could not verify"));
  }, [code]);

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-4 py-10 text-[#1c1917]">
      <article className="mx-auto max-w-lg rounded-md border border-[#0B2A4A] bg-white p-8 shadow-sm">
        <p className="text-center text-[11px] uppercase tracking-[0.22em] text-[#0B2A4A]">Campus record check</p>
        <h1 className="mt-2 text-center text-2xl font-semibold text-[#0B2A4A]">Acknowledgement verification</h1>
        {err ? <p className="mt-6 text-center text-sm text-red-700">{err}</p> : null}
        {!row && !err ? <p className="mt-6 text-center text-sm text-slate-500">Checking the code…</p> : null}
        {row ? (
          <div className="mt-6 space-y-3 text-sm">
            <p className="text-center text-emerald-800">This acknowledgement was issued by the institute.</p>
            <dl className="divide-y border-y">
              <div className="flex justify-between gap-4 py-2"><dt>Number</dt><dd className="font-mono font-semibold">{row.number}</dd></div>
              <div className="flex justify-between gap-4 py-2"><dt>Document</dt><dd className="text-right">{row.title}</dd></div>
              <div className="flex justify-between gap-4 py-2"><dt>Status</dt><dd className="uppercase">{row.status || "recorded"}</dd></div>
              <div className="flex justify-between gap-4 py-2"><dt>Issued</dt><dd>{(row.issued_at || "").replace("T", " ").slice(0, 16)} UTC</dd></div>
            </dl>
            <p className="text-xs leading-5 text-slate-600">The code confirms the number, title, and status. It does not show the filled answers or the person’s contact details.</p>
          </div>
        ) : null}
      </article>
    </main>
  );
}
