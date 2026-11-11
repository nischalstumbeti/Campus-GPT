"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { QRCodeSVG } from "qrcode.react";

type Slip = {
  number: string;
  title: string;
  summary: string;
  email: string;
  email_sent: boolean;
  status?: string;
  layout_kind?: string;
  created_at: string;
  verify_path?: string;
};

type Sheet = { title: string; name: string; identity: string; status: string; fields: { label: string; value: string }[] };

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
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [paper, setPaper] = useState<"ack" | "sheet">("ack");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!number) return;
    apiFetch<Slip>(`/api/v1/acknowledgements/${number}`)
      .then((row) => {
        setSlip(row);
        const kind = row.layout_kind || "general";
        apiFetch<Layout>(`/api/v1/slips/layout?kind=${kind}`).then(setLayout).catch(() => setLayout(FALLBACK));
        if (kind === "form") {
          apiFetch<Sheet & { slip?: Layout }>(`/api/v1/forms/sheet/${number}`).then((data) => {
            setSheet(data);
            if (data.slip?.institution) setLayout({ ...FALLBACK, ...data.slip });
          }).catch(() => setSheet(null));
        }
      })
      .catch((e) => setErr(e.message));
  }, [number]);

  const lines = (slip?.summary || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const verifyUrl = slip?.verify_path ? `${typeof window === "undefined" ? "" : window.location.origin}${slip.verify_path}` : "";

  return (
    <AppShell>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .paper-on, .paper-on * { visibility: visible; }
          .paper-on { position: absolute; left: 0; top: 0; width: 190mm; margin: 0; box-shadow: none; }
          .no-print { display: none !important; }
        }
      `}</style>
      {err ? <p className="text-sm text-red-600">{err}</p> : null}
      {!slip && !err ? <p className="text-sm text-slate-500">Loading slip…</p> : null}
      {slip ? (
        <div>
          <div className="no-print mb-3 flex gap-2">
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setPaper("ack")}>Acknowledgement</button>
            {sheet ? <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setPaper("sheet")}>Filled response</button> : null}
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => window.print()}>Print</button>
            <Link href="/ack" className="px-3 py-1.5 rounded border text-sm">All slips</Link>
          </div>
          <article className={`${paper === "ack" ? "paper-on" : "hidden"} ack-sheet mx-auto bg-white text-black`} style={{ width: "190mm", minHeight: "260mm", padding: "14mm", border: "1px solid #111" }}>
            <div style={{ border: "4px double #0B2A4A", minHeight: "232mm", padding: "12mm", display: "flex", flexDirection: "column" }}>
              <div style={{ borderBottom: "2px solid #0B2A4A", paddingBottom: "8px", textAlign: "center" }}>
                <p className="text-[11px] tracking-[0.22em] uppercase text-[#0B2A4A]">{layout.subtitle}</p>
                <h1 className="mt-1 text-[22px] font-bold leading-tight text-[#0B2A4A]">{layout.institution}</h1>
                <p className="mt-3 text-sm font-semibold tracking-[0.32em]">{layout.document_title}</p>
              </div>
              <div className="mt-4 flex items-start justify-between gap-4 text-sm">
                <div>
                  <p>Acknowledgement no.</p>
                  <p className="font-mono text-base font-semibold">{slip.number}</p>
                  <p className="mt-2">{slip.title}</p>
                  <p className="mt-1">Status: <strong className="uppercase">{slip.status || "recorded"}</strong></p>
                  <p className="mt-1">Issued: {slip.created_at.replace("T", " ").slice(0, 16)} UTC</p>
                </div>
                {verifyUrl ? (
                  <div className="text-center">
                    <QRCodeSVG value={verifyUrl} size={108} includeMargin />
                    <p className="mt-1 text-[10px] tracking-wide">SCAN TO VERIFY</p>
                  </div>
                ) : null}
              </div>
              <table className="mt-5 w-full text-sm" style={{ borderCollapse: "collapse" }}>
                <tbody>
                  {lines.map((line) => {
                    const split = line.indexOf(": ");
                    const label = split > 0 ? line.slice(0, split) : "Particular";
                    const value = split > 0 ? line.slice(split + 2) : line;
                    return (
                      <tr key={line}>
                        <th className="w-2/5 py-2 pr-3 text-left font-medium align-top" style={{ borderBottom: "1px solid #cbd5e1" }}>{label}</th>
                        <td className="py-2 align-top" style={{ borderBottom: "1px solid #cbd5e1" }}>{value}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-5 text-sm leading-6">This acknowledgement is issued from the campus record. The code confirms the number, title, and status. It does not open the filled answers.</p>
              <p className="mt-2 text-xs">A copy is addressed to {slip.email || "the account on record"}{slip.email_sent ? "." : ". Email delivery is not configured, so the slip on this page is the record."}</p>
              <div className="mt-auto pt-12 flex justify-end">
                <div className="text-center text-sm" style={{ minWidth: "55mm" }}>
                  <div style={{ borderTop: "1px solid #111", paddingTop: "6px" }}>
                    <p className="font-semibold">{layout.signatory}</p>
                    <p>{layout.signatory_title}</p>
                  </div>
                </div>
              </div>
              <p className="mt-8 text-center text-[11px]">{layout.footer}</p>
            </div>
          </article>
          {sheet ? (
            <article className={`${paper === "sheet" ? "paper-on" : "hidden"} mx-auto mt-4 bg-white text-black`} style={{ width: "190mm", minHeight: "250mm", padding: "12mm", border: "1px solid #111" }}>
              <div style={{ border: "3px double #111", minHeight: "226mm", padding: "10mm" }}>
                <p className="text-center text-sm font-semibold tracking-[0.2em]">FILLED RESPONSE</p>
                <h1 className="mt-2 text-center text-xl font-bold">{sheet.title}</h1>
                <div className="mt-4 flex justify-between text-sm">
                  <p>{sheet.name} · {sheet.identity}</p>
                  <p>Ack. no. <span className="font-mono font-semibold">{slip.number}</span></p>
                </div>
                <table className="mt-4 w-full text-sm">
                  <tbody>
                    {sheet.fields.map((field) => (
                      <tr key={field.label} className="border-b border-slate-300">
                        <th className="w-2/5 py-2 pr-3 text-left font-medium align-top">{field.label}</th>
                        <td className="py-2 align-top">{field.value || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-6 text-sm">Status: {sheet.status || "submitted"}</p>
              </div>
            </article>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
