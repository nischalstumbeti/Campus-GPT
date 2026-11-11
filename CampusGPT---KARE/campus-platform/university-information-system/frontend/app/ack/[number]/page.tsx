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
  status?: string;
  created_at: string;
};

type Layout = {
  institution: string;
  document_title: string;
  subtitle: string;
  footer: string;
  signatory: string;
  signatory_title: string;
};

const FALLBACK: Layout = {
  institution: "Kalasalingam Academy of Research and Education",
  document_title: "ACKNOWLEDGEMENT",
  subtitle: "University Information System",
  footer: "This acknowledgement is generated from the institute record.",
  signatory: "Registrar",
  signatory_title: "Office of the Registrar",
};

export default function AcknowledgementPage() {
  const params = useParams();
  const number = String(params.number || "");
  const [slip, setSlip] = useState<Slip | null>(null);
  const [layout, setLayout] = useState<Layout>(FALLBACK);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!number) return;
    apiFetch<Slip>(`/api/v1/acknowledgements/${number}`).then(setSlip).catch((e) => setErr(e.message));
    apiFetch<Layout>("/api/v1/slips/layout").then(setLayout).catch(() => setLayout(FALLBACK));
  }, [number]);

  const lines = (slip?.summary || "").split("\n").map((line) => line.trim()).filter(Boolean);

  return (
    <AppShell>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .ack-sheet, .ack-sheet * { visibility: visible; }
          .ack-sheet { position: absolute; left: 0; top: 0; width: 190mm; margin: 0; box-shadow: none; }
          .no-print { display: none !important; }
        }
      `}</style>
      {err ? <p className="text-sm text-red-600">{err}</p> : null}
      {!slip && !err ? <p className="text-sm text-slate-500">Loading slip…</p> : null}
      {slip ? (
        <div>
          <div className="no-print mb-3 flex gap-2">
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => window.print()}>Print</button>
            <Link href="/ack" className="px-3 py-1.5 rounded border text-sm">All slips</Link>
          </div>
          <article className="ack-sheet mx-auto bg-white text-black" style={{ width: "190mm", minHeight: "250mm", padding: "12mm", border: "1px solid #111" }}>
            <div style={{ border: "3px double #111", minHeight: "226mm", padding: "10mm" }}>
              <p className="text-center text-[11px] tracking-[0.18em] uppercase">{layout.subtitle}</p>
              <h1 className="mt-1 text-center text-xl font-bold">{layout.institution}</h1>
              <p className="mt-4 text-center text-sm font-semibold tracking-[0.28em]">{layout.document_title}</p>
              <div className="mt-4 flex justify-between text-sm">
                <p>No. <span className="font-mono font-semibold">{slip.number}</span></p>
                <p>{slip.created_at.replace("T", " ").slice(0, 16)} UTC</p>
              </div>
              <div className="mt-3 flex justify-between border-y border-black py-2 text-sm">
                <p>{slip.title}</p>
                <p>Status: <strong>{slip.status || "recorded"}</strong></p>
              </div>
              <table className="mt-4 w-full text-sm">
                <tbody>
                  {lines.map((line) => {
                    const split = line.indexOf(": ");
                    const label = split > 0 ? line.slice(0, split) : "Particular";
                    const value = split > 0 ? line.slice(split + 2) : line;
                    return (
                      <tr key={line} className="border-b border-slate-300">
                        <th className="w-2/5 py-2 pr-3 text-left font-medium align-top">{label}</th>
                        <td className="py-2 align-top">{value}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-4 text-xs">Copy sent to {slip.email || "the account on record"}{slip.email_sent ? "" : " (email delivery is not configured)"}.</p>
              <div className="mt-16 flex justify-end">
                <div className="text-center text-sm">
                  <p className="font-semibold">{layout.signatory}</p>
                  <p>{layout.signatory_title}</p>
                </div>
              </div>
              <p className="mt-10 text-center text-[11px]">{layout.footer}</p>
            </div>
          </article>
        </div>
      ) : null}
    </AppShell>
  );
}
