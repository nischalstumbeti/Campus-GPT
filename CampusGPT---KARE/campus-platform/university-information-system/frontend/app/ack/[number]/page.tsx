"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { SlipDesign, SlipPaper } from "@/components/SlipPaper";

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
  slip?: Partial<SlipDesign>;
};

type Layout = SlipDesign;

const FALLBACK: Layout = {
  institution: "Kalasalingam Academy of Research and Education",
  subtitle: "University Information System",
  document_title: "ACKNOWLEDGEMENT",
  body: "Number {{number}}\nStatus {{status}}\nDate {{date}}\n\n{{title}}",
  footer: "This page is generated from the campus record.",
  signatory: "Registrar",
  signatory_title: "Office of the Registrar",
  show_particulars: true,
  show_signatory: true,
};

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
        const kind = row.kind && row.kind !== "notice" ? row.kind : "general";
        apiFetch<Layout>(`/api/v1/slips/layout?kind=${encodeURIComponent(kind)}`).then((item) => setLayout({ ...FALLBACK, ...item })).catch(() => setLayout(FALLBACK));
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
  const formDesign = sheet?.slip?.body ? sheet.slip : null;
  const design: Layout = {
    ...layout,
    ...(formDesign ? {
      institution: formDesign.institution || layout.institution,
      subtitle: formDesign.subtitle || layout.subtitle,
      document_title: formDesign.document_title || layout.document_title,
      body: formDesign.body || layout.body || FALLBACK.body,
      footer: formDesign.footer || layout.footer,
      signatory: formDesign.signatory || "",
      signatory_title: formDesign.signatory_title || "",
      show_particulars: formDesign.show_particulars !== false,
      show_signatory: Boolean(formDesign.show_signatory),
    } : {
      document_title: slip?.office?.document_title || layout.document_title,
      body: layout.body || FALLBACK.body,
      signatory: layout.signatory || slip?.office?.signatory || "",
      signatory_title: layout.signatory_title || slip?.office?.signatory_title || "",
      show_signatory: layout.show_signatory,
    }),
  };
  const profile = sheet?.profile || [];
  const answers = sheet?.answers?.length ? sheet.answers : (sheet?.fields || []).filter((field) => !profile.some((item) => item.label === field.label));
  const detailLines = [...profile, ...(answers.length ? answers : lines)];

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
          <div className="paper-on">
            <SlipPaper
              design={design}
              tokens={{ number: slip.number, title: sheet?.title || slip.title, status: slip.status || "recorded", date: slip.created_at.replace("T", " ").slice(0, 16), name: sheet?.name || "", email: slip.email || "" }}
              lines={detailLines}
              verify={verifyUrl}
              note={formDesign ? undefined : slip.office?.reason}
            />
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
