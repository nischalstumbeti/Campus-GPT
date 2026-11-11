"use client";

import { useEffect, useRef } from "react";
import { QRCodeSVG } from "qrcode.react";

export type SlipDesign = {
  kind?: string;
  institution: string;
  subtitle: string;
  document_title: string;
  body: string;
  footer: string;
  signatory: string;
  signatory_title: string;
  show_particulars: boolean;
  show_signatory: boolean;
};

export type SlipLine = { label: string; value: string };

const TOKENS = ["{{number}}", "{{title}}", "{{status}}", "{{date}}", "{{name}}", "{{email}}"];

function sanitize(html: string) {
  return (html || "")
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, "")
    .replace(/<\/?([a-z0-9]+)[^>]*>/gi, (tag, name) => {
      const kept = String(name).toLowerCase();
      if (!["b", "strong", "i", "em", "u", "br", "p", "div"].includes(kept)) return "";
      if (kept === "br") return "<br>";
      return tag.startsWith("</") ? `</${kept}>` : `<${kept}>`;
    });
}

function fill(html: string, tokens: Record<string, string>) {
  const safe = Object.fromEntries(Object.entries(tokens).map(([key, value]) => [key, (value || "").replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] || ch))]));
  return sanitize(html).replace(/\{\{(number|title|status|date|name|email)\}\}/g, (_, key) => safe[key] || "");
}

export function SlipPaper({
  design,
  editing = false,
  onChange,
  tokens = {},
  lines = [],
  verify,
  note,
}: {
  design: SlipDesign;
  editing?: boolean;
  onChange?: (next: SlipDesign) => void;
  tokens?: Record<string, string>;
  lines?: SlipLine[];
  verify?: string;
  note?: string;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const seen = useRef("");
  const set = (patch: Partial<SlipDesign>) => onChange?.({ ...design, ...patch });
  useEffect(() => {
    if (!editing || !bodyRef.current) return;
    if (document.activeElement === bodyRef.current) return;
    const next = design.body || "";
    if (seen.current === next) return;
    bodyRef.current.innerHTML = next;
    seen.current = next;
  }, [design.body, design.kind, editing]);
  const run = (command: string) => {
    bodyRef.current?.focus();
    document.execCommand(command);
    const html = bodyRef.current?.innerHTML || "";
    seen.current = html;
    set({ body: html });
  };

  return (
    <div>
      {editing ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" className="rounded border px-2 py-1 text-sm font-semibold" onClick={() => run("bold")}>B</button>
          <button type="button" className="rounded border px-2 py-1 text-sm italic" onClick={() => run("italic")}>I</button>
          <button type="button" className="rounded border px-2 py-1 text-sm underline" onClick={() => run("underline")}>U</button>
          {TOKENS.map((token) => (
            <button key={token} type="button" className="rounded border px-2 py-1 text-xs" onClick={() => {
              bodyRef.current?.focus();
              document.execCommand("insertText", false, token);
              const html = bodyRef.current?.innerHTML || "";
              seen.current = html;
              set({ body: html });
            }}>{token}</button>
          ))}
          <label className="ml-2 flex items-center gap-1 text-xs"><input type="checkbox" checked={design.show_particulars} onChange={(e) => set({ show_particulars: e.target.checked })} />Particulars</label>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={design.show_signatory} onChange={(e) => set({ show_signatory: e.target.checked })} />Signature</label>
        </div>
      ) : null}
      <article className="mx-auto bg-white text-black" style={{ width: "190mm", minHeight: "250mm", padding: "14mm", border: "1px solid #111" }}>
        <div style={{ border: "2px solid #0B2A4A", minHeight: "222mm", padding: "10mm" }} className="flex flex-col">
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none" }} onBlur={(e) => editing && set({ subtitle: e.currentTarget.textContent || "" })}>
            <p style={{ fontSize: "11px", letterSpacing: "0.16em" }}>{design.subtitle || "University Information System"}</p>
          </div>
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none" }} onBlur={(e) => editing && set({ institution: e.currentTarget.textContent || "" })}>
            <p style={{ fontSize: "20px", fontWeight: 700, color: "#0B2A4A" }}>{design.institution || "Institution"}</p>
          </div>
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none", borderBottom: "2px solid #0B2A4A", paddingBottom: "8px" }} onBlur={(e) => editing && set({ document_title: e.currentTarget.textContent || "" })}>
            <p style={{ marginTop: "8px", fontSize: "14px", fontWeight: 700, letterSpacing: "0.12em" }}>{design.document_title || "ACKNOWLEDGEMENT"}</p>
          </div>
          {editing ? (
            <div
              ref={bodyRef}
              contentEditable
              suppressContentEditableWarning
              style={{ marginTop: "16px", fontSize: "13px", lineHeight: 1.6, outline: "none", minHeight: "40mm", whiteSpace: "pre-wrap" }}
              onBlur={(e) => {
                seen.current = e.currentTarget.innerHTML;
                set({ body: e.currentTarget.innerHTML });
              }}
            />
          ) : (
            <div
              style={{ marginTop: "16px", fontSize: "13px", lineHeight: 1.6, minHeight: "20mm", whiteSpace: "pre-wrap" }}
              dangerouslySetInnerHTML={{ __html: fill(design.body, tokens) || "" }}
            />
          )}
          {note ? <p style={{ marginTop: "12px", fontSize: "12px", lineHeight: 1.5 }}>{note}</p> : null}
          {design.show_particulars && lines.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "12px", fontSize: "12px" }}>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.label}>
                    <th style={{ width: "36%", textAlign: "left", borderBottom: "1px solid #cbd5e1", padding: "6px 8px", background: "#eef3f8" }}>{line.label}</th>
                    <td style={{ borderBottom: "1px solid #cbd5e1", padding: "6px 8px" }}>{line.value || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {design.show_signatory ? (
            <div style={{ marginTop: "18mm", marginLeft: "auto", width: "60mm", textAlign: "center", fontSize: "13px" }}>
              <div contentEditable={editing} suppressContentEditableWarning style={{ borderTop: "1px solid #111", paddingTop: "6px", outline: "none" }} onBlur={(e) => editing && set({ signatory: e.currentTarget.textContent || "" })}>
                <p style={{ fontWeight: 700 }}>{design.signatory || "Signatory"}</p>
              </div>
              <div contentEditable={editing} suppressContentEditableWarning style={{ outline: "none" }} onBlur={(e) => editing && set({ signatory_title: e.currentTarget.textContent || "" })}>
                <p>{design.signatory_title || "Office"}</p>
              </div>
            </div>
          ) : <p style={{ marginTop: "16px", fontSize: "12px" }}>This copy is produced by the campus system and carries no signature.</p>}
          <div contentEditable={editing} suppressContentEditableWarning style={{ marginTop: "auto", paddingTop: "16px", textAlign: "center", fontSize: "10px", outline: "none" }} onBlur={(e) => editing && set({ footer: e.currentTarget.textContent || "" })}>
            <p>{design.footer}</p>
            {verify ? <div style={{ marginTop: "8px" }}>{verify.startsWith("http") ? <QRCodeSVG value={verify} size={72} /> : <p>Verify: {verify}</p>}</div> : null}
          </div>
        </div>
      </article>
    </div>
  );
}
