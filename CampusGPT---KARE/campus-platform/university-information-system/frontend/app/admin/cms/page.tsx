"use client";

import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { API, apiFetch, getToken } from "@/lib/api";
import { noticeText, safeNoticeHref, sanitizeNoticeHtml } from "@/lib/noticeHtml";
import {
  applyBrandingToDocument,
  DEFAULT_BRANDING,
  notifyBrandingChanged,
  notifyMarqueeChanged,
  type Branding,
} from "@/lib/branding";

type MarqueeItem = {
  id: number;
  icon: string;
  description: string;
  link_url?: string;
  active: boolean;
};

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-slate-500">{label}</span>
      <div className="mt-1 flex gap-2 items-center">
        <input
          type="color"
          value={value?.startsWith("#") ? value.slice(0, 7) : "#0B2A4A"}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-12 rounded border cursor-pointer"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 border rounded-lg px-3 py-2 text-sm font-mono"
        />
      </div>
    </label>
  );
}

function NoticeEditor({
  initial,
  onChange,
  maxLinkChars,
}: {
  initial: string;
  onChange: (html: string) => void;
  maxLinkChars?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const range = useRef<Range | null>(null);
  const [linkFor, setLinkFor] = useState("");
  const [hint, setHint] = useState("");

  useEffect(() => {
    if (box.current) box.current.innerHTML = sanitizeNoticeHtml(initial);
    onChange(sanitizeNoticeHtml(initial));
    // Load the saved message once. Later edits stay in the box.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const publish = () => {
    const html = sanitizeNoticeHtml(box.current?.innerHTML || "");
    if (box.current) box.current.innerHTML = html;
    onChange(html);
  };

  const keepSelection = () => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || !box.current?.contains(sel.anchorNode)) {
      range.current = null;
      return;
    }
    range.current = sel.getRangeAt(0).cloneRange();
  };

  const applyLink = () => {
    const selected = range.current;
    const href = safeNoticeHref(linkFor);
    const label = selected?.toString().trim() || "";
    if (!selected || selected.collapsed || !label) {
      setHint("Select a word or phrase in the message first.");
      return;
    }
    if (maxLinkChars && label.length > maxLinkChars) {
      setHint(`A link can cover only a short label, up to ${maxLinkChars} characters.`);
      return;
    }
    if (!href) {
      setHint("Enter a link that starts with https://, http://, mailto:, or /");
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = href;
    if (!href.startsWith("/")) {
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
    }
    anchor.appendChild(selected.extractContents());
    selected.insertNode(anchor);
    setLinkFor("");
    setHint("");
    publish();
  };

  const removeLink = () => {
    const sel = window.getSelection();
    const node = sel?.anchorNode;
    const el = node?.nodeType === Node.TEXT_NODE ? node.parentElement : (node as HTMLElement | null);
    const anchor = el?.closest("a");
    if (!anchor || !box.current?.contains(anchor)) {
      setHint("Place the cursor on a linked word to remove its link.");
      return;
    }
    const parent = anchor.parentNode;
    if (!parent) return;
    while (anchor.firstChild) parent.insertBefore(anchor.firstChild, anchor);
    parent.removeChild(anchor);
    setHint("");
    publish();
  };

  return (
    <div className="space-y-2">
      <div
        ref={box}
        contentEditable
        role="textbox"
        aria-label="Message"
        className="min-h-24 w-full border rounded-lg px-3 py-2 text-sm bg-white [&_a]:underline"
        onMouseUp={keepSelection}
        onKeyUp={keepSelection}
        onInput={() => onChange(sanitizeNoticeHtml(box.current?.innerHTML || ""))}
      />
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={linkFor}
          onChange={(e) => setLinkFor(e.target.value)}
          placeholder="Link for the selected words"
          className="flex-1 min-w-48 border rounded-lg px-3 py-2 text-sm"
        />
        <button type="button" className="px-3 py-2 rounded-lg border text-sm" onMouseDown={(e) => e.preventDefault()} onClick={applyLink}>
          Link selection
        </button>
        <button type="button" className="px-3 py-2 rounded-lg border text-sm" onClick={removeLink}>
          Remove link
        </button>
      </div>
      <p className="text-xs text-slate-500">
        {maxLinkChars
          ? `Write the footer here. Select a short label of up to ${maxLinkChars} characters, then add its link.`
          : "Select a word or phrase, then add its link. The rest of the message stays plain text."}
      </p>
      {hint ? <p className="text-xs text-amber-700">{hint}</p> : null}
    </div>
  );
}

function CmsInner() {
  const search = useSearchParams();
  const [tab, setTab] = useState<"branding" | "marquee">(search.get("tab") === "marquee" ? "marquee" : "branding");
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);
  const [fonts, setFonts] = useState<string[]>([]);
  const [brandMsg, setBrandMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState<MarqueeItem[]>([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ description: "", active: true });
  const [editorKey, setEditorKey] = useState(0);
  const [footerKey, setFooterKey] = useState(0);
  const [editing, setEditing] = useState<MarqueeItem | null>(null);

  const loadBranding = () =>
    apiFetch<{ branding: Branding; fonts?: string[] }>("/api/v1/admin/branding")
      .then((d) => {
        const b = { ...DEFAULT_BRANDING, ...d.branding };
        setBranding(b);
        setFooterKey((key) => key + 1);
        if (d.fonts?.length) setFonts(d.fonts);
        applyBrandingToDocument(b);
      })
      .catch(() => setBrandMsg("Could not load branding."));

  const loadMarquee = () =>
    apiFetch<{ items: MarqueeItem[] }>("/api/v1/admin/marquee")
      .then((d) => {
        setItems(d.items || []);
      })
      .catch(() => setItems([]));

  useEffect(() => {
    loadBranding();
    loadMarquee();
  }, []);

  useEffect(() => {
    setTab(search.get("tab") === "marquee" ? "marquee" : "branding");
  }, [search]);

  const previewStyle = useMemo(
    () => ({
      backgroundColor: branding.bg_light,
      color: branding.text_color,
      fontFamily: branding.font_family,
      fontSize: branding.font_size_base,
      backgroundImage: branding.background_image_url
        ? `linear-gradient(rgba(255,255,255,${branding.background_overlay || 0.9}), rgba(255,255,255,${branding.background_overlay || 0.9})), url(${branding.background_image_url})`
        : undefined,
      backgroundSize: "cover" as const,
    }),
    [branding]
  );

  const saveBranding = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setBrandMsg("");
    try {
      const data = await apiFetch<{ branding: Branding }>("/api/v1/admin/branding", {
        method: "PUT",
        body: JSON.stringify(branding),
      });
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      notifyBrandingChanged();
      setBrandMsg("Branding saved. The theme is now applied across UIS.");
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const uploadBg = async (kind: "app" | "login" | "logo", file: File | null) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    try {
      const res = await fetch(`${API}/api/v1/admin/branding/upload-background?kind=${kind}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || "Upload failed");
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      notifyBrandingChanged();
      setBrandMsg(kind === "logo" ? "Logo uploaded." : "Background uploaded.");
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const clearImage = async (kind: "app" | "login" | "logo") => {
    const token = getToken();
    try {
      const res = await fetch(`${API}/api/v1/admin/branding/clear-image?kind=${kind}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || "Could not remove image");
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      notifyBrandingChanged();
      setBrandMsg(kind === "logo" ? "Logo removed." : "Image removed.");
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Could not remove image");
    }
  };

  const submitMarquee = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      const description = sanitizeNoticeHtml(form.description);
      if (!noticeText(description)) {
        setMsg("Write the notification message.");
        return;
      }
      const payload = { description, active: form.active, link_url: "" };
      if (editing) {
        await apiFetch(`/api/v1/admin/marquee/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setMsg("Updated.");
      } else {
        await apiFetch("/api/v1/admin/marquee", { method: "POST", body: JSON.stringify(payload) });
        setMsg("Added.");
      }
      setForm({ description: "", active: true });
      setEditing(null);
      setEditorKey((n) => n + 1);
      loadMarquee();
      notifyMarqueeChanged();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <AppShell>
      <div className="max-w-4xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-brand">Admin CMS</h1>
          <p className="text-sm text-slate-500">Branding, colors, fonts, backgrounds, and campus notifications.</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTab("branding")}
            className={`px-4 py-2 rounded-lg text-sm ${tab === "branding" ? "bg-brand text-white" : "border"}`}
          >
            Branding & theme
          </button>
          <button
            type="button"
            onClick={() => setTab("marquee")}
            className={`px-4 py-2 rounded-lg text-sm ${tab === "marquee" ? "bg-brand text-white" : "border"}`}
          >
            Notification manager
          </button>
        </div>

        {tab === "branding" && (
          <form onSubmit={saveBranding} className="space-y-4">
            {brandMsg && <p className="text-sm text-emerald-700">{brandMsg}</p>}
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Header, footer, and sign-in</p>
              <label className="block text-sm">
                <span className="text-xs text-slate-500">App name (sidebar)</span>
                <input
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                  value={branding.app_name}
                  onChange={(e) => setBranding({ ...branding, app_name: e.target.value })}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-slate-500">Header title</span>
                <input
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                  value={branding.header_title}
                  onChange={(e) => setBranding({ ...branding, header_title: e.target.value })}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-slate-500">Header subtitle</span>
                <input
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                  value={branding.header_subtitle}
                  onChange={(e) => setBranding({ ...branding, header_subtitle: e.target.value })}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-slate-500">Sign-in button</span>
                <input
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                  value={branding.sign_in_label}
                  onChange={(e) => setBranding({ ...branding, sign_in_label: e.target.value })}
                />
              </label>
              <div className="block text-sm">
                <span className="text-xs text-slate-500">Footer</span>
                <div className="mt-1">
                  <NoticeEditor
                    key={footerKey}
                    initial={branding.footer_text}
                    maxLinkChars={32}
                    onChange={(html) => setBranding((current) => ({ ...current, footer_text: html }))}
                  />
                </div>
              </div>
            </div>
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Logo</p>
              {branding.logo_url ? (
                <img src={branding.logo_url} alt="" className="h-14 w-14 object-contain border rounded-md bg-white" />
              ) : (
                <p className="text-sm text-slate-500">No logo. Upload one to show it, or leave this empty.</p>
              )}
              <input type="file" accept="image/*" onChange={(e) => uploadBg("logo", e.target.files?.[0] || null)} />
              {branding.logo_url ? (
                <button type="button" className="text-sm text-red-700 underline" onClick={() => clearImage("logo")}>
                  Remove logo
                </button>
              ) : null}
            </div>
            <div className="bg-white border rounded-lg p-4 grid sm:grid-cols-2 gap-3">
              <ColorField label="Primary / brand" value={branding.primary} onChange={(v) => setBranding({ ...branding, primary: v })} />
              <ColorField label="Primary dark" value={branding.primary_dark} onChange={(v) => setBranding({ ...branding, primary_dark: v })} />
              <ColorField label="Secondary" value={branding.secondary} onChange={(v) => setBranding({ ...branding, secondary: v })} />
              <ColorField label="Accent / gold" value={branding.accent} onChange={(v) => setBranding({ ...branding, accent: v })} />
              <ColorField label="Page background" value={branding.bg_light} onChange={(v) => setBranding({ ...branding, bg_light: v })} />
              <ColorField label="Text color" value={branding.text_color} onChange={(v) => setBranding({ ...branding, text_color: v })} />
            </div>
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={branding.font_family}
                onChange={(e) => setBranding({ ...branding, font_family: e.target.value })}
              >
                {(fonts.length ? fonts : [branding.font_family]).map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={branding.font_family}
                onChange={(e) => setBranding({ ...branding, font_family: e.target.value })}
              />
              <div className="grid sm:grid-cols-2 gap-3">
                <input
                  className="border rounded-lg px-3 py-2 text-sm"
                  value={branding.font_size_base}
                  onChange={(e) => setBranding({ ...branding, font_size_base: e.target.value })}
                  placeholder="16px"
                />
                <input
                  className="border rounded-lg px-3 py-2 text-sm"
                  value={branding.heading_scale}
                  onChange={(e) => setBranding({ ...branding, heading_scale: e.target.value })}
                  placeholder="1.25"
                />
              </div>
            </div>
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Page background</p>
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={branding.background_overlay}
                onChange={(e) => setBranding({ ...branding, background_overlay: e.target.value })}
                placeholder="Overlay 0-1"
              />
              <label className="block text-sm">
                <span className="text-xs text-slate-500">App background</span>
                <input className="mt-1 block text-sm" type="file" accept="image/*" onChange={(e) => uploadBg("app", e.target.files?.[0] || null)} />
              </label>
              {branding.background_image_url ? (
                <button type="button" className="text-sm text-red-700 underline" onClick={() => clearImage("app")}>
                  Remove app background
                </button>
              ) : null}
              <label className="block text-sm">
                <span className="text-xs text-slate-500">Sign-in background</span>
                <input className="mt-1 block text-sm" type="file" accept="image/*" onChange={(e) => uploadBg("login", e.target.files?.[0] || null)} />
              </label>
              {branding.login_background_url ? (
                <button type="button" className="text-sm text-red-700 underline" onClick={() => clearImage("login")}>
                  Remove sign-in background
                </button>
              ) : null}
            </div>
            <div className="rounded-lg border p-4" style={previewStyle}>
              <p className="text-xs uppercase opacity-70">Preview</p>
              <h2 className="font-bold" style={{ color: branding.primary }}>
                {branding.app_name}
              </h2>
            </div>
            <button type="submit" disabled={saving} className="px-4 py-2 rounded-lg bg-brand text-white text-sm disabled:opacity-60">
              {saving ? "Saving…" : "Save branding"}
            </button>
          </form>
        )}

        {tab === "marquee" && (
          <div className="space-y-4">
            {msg && <p className="text-sm text-emerald-700">{msg}</p>}
            <form onSubmit={submitMarquee} className="bg-white border rounded-lg p-4 space-y-3">
              <div className="block text-sm">
                <span className="text-xs text-slate-500">Message</span>
                <div className="mt-1">
                  <NoticeEditor
                    key={editing ? `edit-${editing.id}-${editorKey}` : `new-${editorKey}`}
                    initial={form.description}
                    onChange={(html) => setForm((current) => ({ ...current, description: html }))}
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
                Active
              </label>
              <button type="submit" className="w-full py-2 rounded-lg bg-brand text-white text-sm">
                {editing ? "Save" : "Add"}
              </button>
            </form>
            <div className="space-y-2">
              {items.map((n) => (
                <div key={n.id} className="bg-white border rounded-lg p-3 flex gap-3">
                  <div
                    className="flex-1 min-w-0 text-sm [&_a]:underline"
                    dangerouslySetInnerHTML={{ __html: sanitizeNoticeHtml(n.description) }}
                  />
                  <button
                    type="button"
                    className="text-xs text-brand underline"
                    onClick={() => {
                      setEditing(n);
                      setForm({ description: n.description, active: n.active });
                      setEditorKey((k) => k + 1);
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="text-xs text-red-700 underline"
                    onClick={async () => {
                      await apiFetch(`/api/v1/admin/marquee/${n.id}`, { method: "DELETE" });
                      if (editing?.id === n.id) {
                        setEditing(null);
                        setForm({ description: "", active: true });
                        setEditorKey((k) => k + 1);
                      }
                      loadMarquee();
                      notifyMarqueeChanged();
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function AdminCmsPage() {
  return (
    <Suspense fallback={<AppShell><p className="text-sm text-slate-500">Loading CMS…</p></AppShell>}>
      <CmsInner />
    </Suspense>
  );
}
