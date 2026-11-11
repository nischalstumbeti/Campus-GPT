"use client";

import { useEffect, useRef, useState } from "react";
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
  page_size?: string;
  orientation?: string;
  font_family?: string;
};

export type SlipLine = { label: string; value: string };

const TOKENS = ["{{number}}", "{{title}}", "{{status}}", "{{date}}", "{{name}}", "{{email}}"];
const FONTS = ["Georgia", "Times New Roman", "Arial", "Calibri", "Courier New", "Verdana"];
const FONT_SIZE: Record<string, string> = { "1": "12px", "2": "14px", "3": "16px", "4": "18px", "5": "20px", "6": "24px", "7": "28px" };
const PAGES: Record<string, { portrait: [string, string]; landscape: [string, string]; label: string }> = {
  a4: { label: "A4", portrait: ["210mm", "297mm"], landscape: ["297mm", "210mm"] },
  a5: { label: "A5", portrait: ["148mm", "210mm"], landscape: ["210mm", "148mm"] },
  letter: { label: "Letter", portrait: ["216mm", "279mm"], landscape: ["279mm", "216mm"] },
  legal: { label: "Legal", portrait: ["216mm", "356mm"], landscape: ["356mm", "216mm"] },
};

function safeStyle(raw: string) {
  const parts: string[] = [];
  const face = raw.match(/face=["']([^"']+)/i)?.[1]?.trim();
  if (face && FONTS.includes(face)) parts.push(`font-family:${face}`);
  const size = raw.match(/size=["']?([1-7])/i)?.[1];
  if (size) parts.push(`font-size:${FONT_SIZE[size]}`);
  const style = raw.match(/style=["']([^"']*)/i)?.[1] || "";
  const family = style.match(/font-family:\s*([^;]+)/i)?.[1]?.trim().replace(/['"]/g, "");
  if (family && FONTS.includes(family)) parts.push(`font-family:${family}`);
  const pixels = style.match(/font-size:\s*(12|14|16|18|20|24|28)px/i)?.[1];
  if (pixels) parts.push(`font-size:${pixels}px`);
  const align = (style.match(/text-align:\s*(left|center|right|justify)/i) || raw.match(/align=["'](left|center|right|justify)/i))?.[1];
  if (align) parts.push(`text-align:${align.toLowerCase()}`);
  const kept = new Map<string, string>();
  parts.forEach((part) => {
    const [key, value] = part.split(":");
    kept.set(key, value);
  });
  return Array.from(kept.entries()).map(([key, value]) => `${key}:${value}`).join(";");
}

function sanitize(html: string) {
  return (html || "")
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, "")
    .replace(/<\/?([a-z0-9]+)[^>]*>/gi, (tag, name) => {
      let kept = String(name).toLowerCase();
      if (kept === "font") kept = "span";
      if (!["b", "strong", "i", "em", "u", "br", "p", "div", "span", "h1", "h2", "h3", "ul", "ol", "li", "img"].includes(kept)) return "";
      if (kept === "img") {
        const src = tag.match(/src=["'](https:\/\/[^"']+)/i)?.[1];
        return src ? `<img src="${src}" alt="" style="max-width:80mm;height:auto">` : "";
      }
      if (kept === "br") return "<br>";
      if (tag.startsWith("</")) return `</${kept}>`;
      const style = safeStyle(tag);
      if (style && ["span", "p", "div", "h1", "h2", "h3"].includes(kept)) return `<${kept} style="${style}">`;
      return `<${kept}>`;
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
  const htmlRef = useRef<HTMLTextAreaElement>(null);
  const seen = useRef("");
  const [htmlMode, setHtmlMode] = useState(false);
  const set = (patch: Partial<SlipDesign>) => onChange?.({ ...design, ...patch });
  const pageKey = PAGES[design.page_size || "a4"] ? design.page_size || "a4" : "a4";
  const orientation = design.orientation === "landscape" ? "landscape" : "portrait";
  const font = FONTS.includes(design.font_family || "") ? design.font_family || "Georgia" : "Georgia";
  const [pageWidth, pageHeight] = PAGES[pageKey][orientation];
  useEffect(() => {
    if (!editing || htmlMode || !bodyRef.current) return;
    if (document.activeElement === bodyRef.current) return;
    const next = design.body || "";
    if (seen.current === next) return;
    bodyRef.current.innerHTML = next;
    seen.current = next;
  }, [design.body, design.kind, editing, htmlMode]);
  const remember = (html: string) => {
    seen.current = html;
    set({ body: html });
  };
  const run = (command: string, value?: string) => {
    if (htmlMode) return;
    bodyRef.current?.focus();
    document.execCommand(command, false, value);
    remember(bodyRef.current?.innerHTML || "");
  };
  const wrapHtml = (open: string, close: string) => {
    const box = htmlRef.current;
    if (!box) return;
    const start = box.selectionStart;
    const end = box.selectionEnd;
    const next = `${design.body.slice(0, start)}${open}${design.body.slice(start, end)}${close}${design.body.slice(end)}`;
    remember(next);
  };

  return (
    <div>
      {editing ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <label className="text-xs text-slate-500">Font
            <select className="ml-1 border rounded px-1 py-1 text-sm" value={font} onChange={(e) => {
              if (!htmlMode) {
                bodyRef.current?.focus();
                document.execCommand("fontName", false, e.target.value);
                seen.current = bodyRef.current?.innerHTML || design.body;
              }
              set({ font_family: e.target.value, body: seen.current || design.body });
            }}>
              {FONTS.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-500">Size
            <select className="ml-1 border rounded px-1 py-1 text-sm" defaultValue="3" onChange={(e) => htmlMode ? wrapHtml(`<span style="font-size:${FONT_SIZE[e.target.value]}">`, "</span>") : run("fontSize", e.target.value)}>
              <option value="1">12</option>
              <option value="2">14</option>
              <option value="3">16</option>
              <option value="4">18</option>
              <option value="5">20</option>
              <option value="6">24</option>
              <option value="7">28</option>
            </select>
          </label>
          <button type="button" className="rounded border px-2 py-1 text-sm font-bold" onClick={() => htmlMode ? wrapHtml("<b>", "</b>") : run("bold")}>Bold</button>
          <button type="button" className="rounded border px-2 py-1 text-sm italic" onClick={() => htmlMode ? wrapHtml("<i>", "</i>") : run("italic")}>Italic</button>
          <button type="button" className="rounded border px-2 py-1 text-sm underline" onClick={() => htmlMode ? wrapHtml("<u>", "</u>") : run("underline")}>Underline</button>
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => run("justifyLeft")}>Left</button>
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => run("justifyCenter")}>Center</button>
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => run("justifyRight")}>Right</button>
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => {
            const url = window.prompt("Image address, starting with https://");
            if (!url || !/^https:\/\//i.test(url)) return;
            const html = `<img src="${url.replace(/"/g, "")}" alt="" style="max-width:80mm;height:auto">`;
            if (htmlMode) wrapHtml(html, "");
            else run("insertHTML", html);
          }}>Image</button>
          <label className="text-xs text-slate-500">Page
            <select className="ml-1 border rounded px-1 py-1 text-sm" value={pageKey} onChange={(e) => set({ page_size: e.target.value })}>
              {Object.entries(PAGES).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-500">Orientation
            <select className="ml-1 border rounded px-1 py-1 text-sm" value={orientation} onChange={(e) => set({ orientation: e.target.value })}>
              <option value="portrait">Portrait</option>
              <option value="landscape">Landscape</option>
            </select>
          </label>
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => { setHtmlMode((current) => !current); seen.current = ""; }}>{htmlMode ? "Page view" : "HTML"}</button>
          {TOKENS.map((token) => (
            <button key={token} type="button" className="rounded border px-2 py-1 text-xs" onClick={() => {
              if (htmlMode) wrapHtml(token, "");
              else {
                bodyRef.current?.focus();
                document.execCommand("insertText", false, token);
                remember(bodyRef.current?.innerHTML || "");
              }
            }}>{token}</button>
          ))}
          <label className="ml-2 flex items-center gap-1 text-xs"><input type="checkbox" checked={design.show_particulars} onChange={(e) => set({ show_particulars: e.target.checked })} />Particulars</label>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={design.show_signatory} onChange={(e) => set({ show_signatory: e.target.checked })} />Signature</label>
        </div>
      ) : null}
      <style>{`@page { size: ${pageKey === "letter" || pageKey === "legal" ? pageKey : pageKey.toUpperCase()} ${orientation}; }`}</style>
      <article className="mx-auto bg-white text-black" style={{ width: pageWidth, minHeight: pageHeight, padding: "12mm", border: "1px solid #111", fontFamily: font }}>
        <div style={{ border: "2px solid #0B2A4A", minHeight: `calc(${pageHeight} - 32mm)`, padding: "10mm" }} className="flex flex-col">
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none" }} onBlur={(e) => editing && set({ subtitle: e.currentTarget.textContent || "" })}>
            <p style={{ fontSize: "11px", letterSpacing: "0.16em" }}>{design.subtitle || "University Information System"}</p>
          </div>
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none" }} onBlur={(e) => editing && set({ institution: e.currentTarget.textContent || "" })}>
            <p style={{ fontSize: "20px", fontWeight: 700, color: "#0B2A4A" }}>{design.institution || "Institution"}</p>
          </div>
          <div contentEditable={editing} suppressContentEditableWarning style={{ textAlign: "center", outline: "none", borderBottom: "2px solid #0B2A4A", paddingBottom: "8px" }} onBlur={(e) => editing && set({ document_title: e.currentTarget.textContent || "" })}>
            <p style={{ marginTop: "8px", fontSize: "14px", fontWeight: 700, letterSpacing: "0.12em" }}>{design.document_title || "ACKNOWLEDGEMENT"}</p>
          </div>
          {editing && htmlMode ? (
            <textarea
              ref={htmlRef}
              className="mt-4 w-full border border-slate-300 p-2 text-sm"
              style={{ minHeight: "40mm", fontFamily: font }}
              value={design.body || ""}
              onChange={(e) => remember(e.target.value)}
            />
          ) : editing ? (
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
              style={{ marginTop: "16px", fontSize: "16px", lineHeight: 1.6, minHeight: "20mm", whiteSpace: "pre-wrap" }}
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
