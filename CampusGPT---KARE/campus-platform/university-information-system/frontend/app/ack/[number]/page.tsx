"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { QRCodeSVG } from "qrcode.react";

type Office = { document_title: string; signatory: string; signatory_title: string; reason: string };

type Slip = {
  number: string;
  title: string;
  summary: string;
  email: string;
  email_sent: boolean;
  status?: string;
  kind?: string;
  layout_kind?: string;
  office?: Office | null;
  created_at: string;
  verify_path?: string;
};

type Line = { label: string; value: string };

type Sheet = {
  title: string;
  name: string;
  identity: string;
  status: string;
  photo_url?: string;
  profile?: Line[];
  answers?: Line[];
  fields: Line[];
  slip?: { institution?: string };
};

type Layout = { institution: string; subtitle: string; footer: string };

const FALLBACK: Layout = {
  institution: "Kalasalingam Academy of Research and Education",
  subtitle: "University Information System",
  footer: "This page is generated from the campus record.",
};

const cell = { border: "1px solid #111", padding: "6px 8px", fontSize: "12px", verticalAlign: "top" as const };
const labelCell = { ...cell, width: "34%", background: "#eef3f8", fontWeight: 600 };

function Rows({ lines }: { lines: Line[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        {lines.map((line) => (
          <tr key={line.label}>
            <th style={labelCell}>{line.label}</th>
            <td style={cell}>{line.value || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AcknowledgementPage() {
  const params = useParams();
  const number = String(params.number || "");
  const [slip, setSlip] = useState<Slip | null>(null);
  const [layout, setLayout] = useState<Layout>(FALLBACK);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!number) return;
    apiFetch<Slip>(`/api/v1/acknowledgements/${number}`)
      .then((row) => {
        setSlip(row);
        const kind = row.layout_kind === "form" ? "form" : "general";
        apiFetch<Layout>(`/api/v1/slips/layout?kind=${kind}`).then(setLayout).catch(() => setLayout(FALLBACK));
        if (row.layout_kind === "form") {
          apiFetch<Sheet>(`/api/v1/forms/sheet/${number}`).then(setSheet).catch(() => setSheet(null));
        }
      })
      .catch((e) => setErr(e.message));
  }, [number]);

  const lines = (slip?.summary || "").split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
    const split = line.indexOf(": ");
    return split > 0 ? { label: line.slice(0, split), value: line.slice(split + 2) } : { label: "Particular", value: line };
  });
  const verifyUrl = slip?.verify_path && typeof window !== "undefined" ? `${window.location.origin}${slip.verify_path}` : "";
  const formSlip = slip?.layout_kind === "form";
  const profile = sheet?.profile?.length ? sheet.profile : [];
  const answers = sheet?.answers?.length ? sheet.answers : (sheet?.fields || []).filter((field) => !profile.some((item) => item.label === field.label));
  const institution = sheet?.slip?.institution || layout.institution || FALLBACK.institution;

  return (
    <AppShell>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .paper-on, .paper-on * { visibility: visible; }
          .paper-on { position: absolute; left: 0; top: 0; width: 190mm; margin: 0; }
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
          {formSlip ? (
            <article className="paper-on mx-auto bg-white text-black" style={{ width: "190mm", minHeight: "270mm", padding: "10mm" }}>
              <div style={{ border: "2px solid #0B2A4A" }}>
                <div style={{ background: "#0B2A4A", color: "#fff", textAlign: "center", padding: "12px 14px" }}>
                  <p style={{ fontSize: "11px", letterSpacing: "0.18em" }}>{layout.subtitle || FALLBACK.subtitle}</p>
                  <p style={{ fontSize: "18px", fontWeight: 700, marginTop: "4px" }}>{institution}</p>
                  <p style={{ fontSize: "15px", fontWeight: 700, letterSpacing: "0.16em", marginTop: "8px" }}>APPLICATION CONFIRMATION</p>
                  <p style={{ fontSize: "13px", marginTop: "4px" }}>{sheet?.title || slip.title}</p>
                </div>
                <div style={{ display: "flex", borderBottom: "1px solid #111" }}>
                  <div style={{ flex: 1, padding: "10px 12px" }}>
                    <p style={{ fontSize: "11px" }}>Application number</p>
                    <p style={{ fontFamily: "ui-monospace, monospace", fontSize: "18px", fontWeight: 700 }}>{slip.number}</p>
                    <p style={{ display: "inline-block", marginTop: "8px", background: "#e8f5e9", border: "1px solid #1b5e20", color: "#1b5e20", fontSize: "12px", fontWeight: 700, padding: "2px 8px" }}>SUCCESSFULLY SUBMITTED</p>
                    <p style={{ fontSize: "12px", marginTop: "8px" }}>Submitted on {slip.created_at.replace("T", " ").slice(0, 16)} UTC</p>
                    <p style={{ fontSize: "12px", marginTop: "2px" }}>{sheet?.name || ""}{sheet?.identity ? ` · ${sheet.identity}` : ""}</p>
                  </div>
                  <div style={{ width: "32mm", borderLeft: "1px solid #111", display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", fontSize: "11px", padding: "6px" }}>
                    {sheet?.photo_url ? <img src={sheet.photo_url} alt="" style={{ width: "28mm", height: "36mm", objectFit: "cover" }} /> : <span>Photograph<br />as on the campus record</span>}
                  </div>
                  <div style={{ width: "34mm", borderLeft: "1px solid #111", textAlign: "center", padding: "6px" }}>
                    {verifyUrl ? <QRCodeSVG value={verifyUrl} size={96} /> : null}
                    <p style={{ fontSize: "9px", marginTop: "4px" }}>Scan to verify</p>
                  </div>
                </div>
                {profile.length ? (
                  <>
                    <p style={{ background: "#0B2A4A", color: "#fff", fontSize: "12px", fontWeight: 700, padding: "4px 8px" }}>Particulars of the applicant</p>
                    <Rows lines={profile} />
                  </>
                ) : null}
                <p style={{ background: "#0B2A4A", color: "#fff", fontSize: "12px", fontWeight: 700, padding: "4px 8px" }}>Details submitted in this application</p>
                <Rows lines={answers.length ? answers : lines} />
                <p style={{ fontSize: "11px", lineHeight: 1.5, padding: "10px 12px" }}>
                  This confirmation is only for the form named above. It is produced by the campus system when the form is submitted. It is not an order of the Dean, the Controller of Examinations, or any other office, and it carries no signature.
                  {" "}The code confirms this application number. It does not open the answers to anyone else.
                </p>
                <p style={{ fontSize: "10px", textAlign: "center", padding: "0 12px 10px" }}>{layout.footer || FALLBACK.footer}</p>
              </div>
            </article>
          ) : (
            <article className="paper-on mx-auto bg-white text-black" style={{ width: "190mm", minHeight: "260mm", padding: "12mm" }}>
              <div style={{ border: "2px solid #0B2A4A", minHeight: "236mm", padding: "10mm", display: "flex", flexDirection: "column" }}>
                <div style={{ textAlign: "center", borderBottom: "2px solid #0B2A4A", paddingBottom: "8px" }}>
                  <p style={{ fontSize: "11px", letterSpacing: "0.18em" }}>{layout.subtitle || FALLBACK.subtitle}</p>
                  <p style={{ fontSize: "20px", fontWeight: 700, color: "#0B2A4A" }}>{institution}</p>
                  <p style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "0.14em", marginTop: "8px" }}>{slip.office?.document_title || "ACKNOWLEDGEMENT"}</p>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", marginTop: "12px" }}>
                  <div style={{ fontSize: "13px" }}>
                    <p>Acknowledgement no. <strong style={{ fontFamily: "ui-monospace, monospace" }}>{slip.number}</strong></p>
                    <p style={{ marginTop: "4px" }}>{slip.title}</p>
                    <p style={{ marginTop: "4px" }}>Status: <strong>{(slip.status || "recorded").toUpperCase()}</strong></p>
                    <p style={{ marginTop: "4px" }}>Issued: {slip.created_at.replace("T", " ").slice(0, 16)} UTC</p>
                  </div>
                  {verifyUrl ? <div style={{ textAlign: "center" }}><QRCodeSVG value={verifyUrl} size={88} /><p style={{ fontSize: "9px" }}>Scan to verify</p></div> : null}
                </div>
                <div style={{ marginTop: "12px" }}><Rows lines={lines} /></div>
                {slip.office ? (
                  <div style={{ marginTop: "16px", border: "1px solid #111", padding: "8px 10px", fontSize: "12px" }}>
                    <p>{slip.office.reason}</p>
                    <p style={{ marginTop: "10px" }}>For {slip.office.signatory_title}</p>
                    <p style={{ marginTop: "28px", fontWeight: 700 }}>{slip.office.signatory}</p>
                  </div>
                ) : null}
                <p style={{ marginTop: "auto", paddingTop: "16px", fontSize: "10px", textAlign: "center" }}>{layout.footer || FALLBACK.footer}</p>
              </div>
            </article>
          )}
        </div>
      ) : null}
    </AppShell>
  );
}
