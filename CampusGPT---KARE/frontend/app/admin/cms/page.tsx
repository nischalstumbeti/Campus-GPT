"use client";

import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiDelete, apiGet, apiPost, apiPut, authHeaders } from "@/lib/api";
import { applyBrandingToDocument, DEFAULT_BRANDING, type Branding } from "@/lib/branding";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

type MarqueeItem = {
  id: number;
  icon: string;
  description: string;
  active: boolean;
  sort_order: number;
};

const FALLBACK_ICONS = ["📢", "⚠️", "🎓", "🏫", "📅", "💰", "🚌", "🏆", "🔔", "ℹ️"];

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="mt-1 flex gap-2 items-center">
        <input
          type="color"
          value={value?.startsWith("#") ? value.slice(0, 7) : "#7C5AED"}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-12 rounded border border-gray-200 cursor-pointer bg-white"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 border rounded-xl px-3 py-2 text-sm font-mono"
        />
      </div>
    </label>
  );
}

function CmsInner() {
  const search = useSearchParams();
  const initialTab = search.get("tab") === "marquee" ? "marquee" : "branding";
  const [tab, setTab] = useState<"branding" | "marquee">(initialTab);

  // Branding state
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);
  const [fonts, setFonts] = useState<string[]>([]);
  const [brandMsg, setBrandMsg] = useState("");
  const [savingBrand, setSavingBrand] = useState(false);

  // Marquee state
  const [items, setItems] = useState<MarqueeItem[]>([]);
  const [icons, setIcons] = useState<string[]>(FALLBACK_ICONS);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ icon: "📢", description: "", active: true });
  const [editing, setEditing] = useState<MarqueeItem | null>(null);

  const loadBranding = () =>
    apiGet<{ branding: Branding; fonts?: string[] }>("/api/admin/branding")
      .then((d) => {
        const b = { ...DEFAULT_BRANDING, ...d.branding };
        setBranding(b);
        if (d.fonts?.length) setFonts(d.fonts);
        applyBrandingToDocument(b);
      })
      .catch(() => setBrandMsg("Could not load branding."));

  const loadMarquee = () =>
    apiGet<{ items: MarqueeItem[]; icons?: string[] }>("/api/admin/marquee")
      .then((d) => {
        setItems(d.items || []);
        if (d.icons?.length) setIcons(d.icons);
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
        ? `linear-gradient(rgba(255,255,255,${branding.background_overlay || 0.88}), rgba(255,255,255,${branding.background_overlay || 0.88})), url(${branding.background_image_url})`
        : undefined,
      backgroundSize: "cover",
      backgroundPosition: "center",
    }),
    [branding]
  );

  const saveBranding = async (e: FormEvent) => {
    e.preventDefault();
    setSavingBrand(true);
    setBrandMsg("");
    try {
      const data = await apiPut<{ branding: Branding }>("/api/admin/branding", branding);
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      setBrandMsg("Branding saved — applied across the app.");
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingBrand(false);
    }
  };

  const resetBranding = async () => {
    setSavingBrand(true);
    setBrandMsg("");
    try {
      const data = await apiPost<{ branding: Branding }>("/api/admin/branding/reset", {});
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      setBrandMsg("Reset to defaults.");
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setSavingBrand(false);
    }
  };

  const uploadBg = async (kind: "app" | "login", file: File | null) => {
    if (!file) return;
    setBrandMsg("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const headers = authHeaders();
      delete headers["Content-Type"];
      const res = await fetch(`${API_BASE}/api/admin/branding/upload-background?kind=${kind}`, {
        method: "POST",
        headers: { Authorization: headers.Authorization || "" },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || "Upload failed");
      const b = { ...DEFAULT_BRANDING, ...data.branding };
      setBranding(b);
      applyBrandingToDocument(b);
      setBrandMsg(`${kind === "login" ? "Login" : "App"} background uploaded.`);
    } catch (err) {
      setBrandMsg(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const submitMarquee = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      if (editing) {
        await apiPut(`/api/admin/marquee/${editing.id}`, {
          icon: form.icon,
          description: form.description,
          active: form.active,
        });
        setMsg("Marquee item updated.");
      } else {
        await apiPost("/api/admin/marquee", form);
        setMsg("Marquee item added.");
      }
      setForm({ icon: "📢", description: "", active: true });
      setEditing(null);
      loadMarquee();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  };

  const removeMarquee = async (id: number) => {
    await apiDelete(`/api/admin/marquee/${id}`);
    setMsg("Removed.");
    if (editing?.id === id) {
      setEditing(null);
      setForm({ icon: "📢", description: "", active: true });
    }
    loadMarquee();
  };

  return (
    <CopilotShell title="Admin CMS">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-primary">Admin CMS</h1>
          <p className="text-sm text-gray-600">
            Admin login only — manage branding (colors, fonts, backgrounds) and the campus marquee ticker.
          </p>
        </div>

        <div className="flex gap-2 border-b border-gray-100 pb-2">
          <button
            type="button"
            onClick={() => setTab("branding")}
            className={`px-4 py-2 rounded-xl text-sm font-medium ${
              tab === "branding" ? "bg-primary text-white" : "bg-gray-50 text-gray-700"
            }`}
          >
            Branding & theme
          </button>
          <button
            type="button"
            onClick={() => setTab("marquee")}
            className={`px-4 py-2 rounded-xl text-sm font-medium ${
              tab === "marquee" ? "bg-primary text-white" : "bg-gray-50 text-gray-700"
            }`}
          >
            Marquee ticker
          </button>
        </div>

        {tab === "branding" && (
          <form onSubmit={saveBranding} className="space-y-6">
            {brandMsg && <p className="text-sm text-emerald-700">{brandMsg}</p>}

            <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">App identity</p>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">App name</span>
                <input
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.app_name}
                  onChange={(e) => setBranding({ ...branding, app_name: e.target.value })}
                />
              </label>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">Color palette</p>
              <div className="grid sm:grid-cols-2 gap-3">
                <ColorField label="Primary" value={branding.primary} onChange={(v) => setBranding({ ...branding, primary: v })} />
                <ColorField label="Primary dark" value={branding.primary_dark} onChange={(v) => setBranding({ ...branding, primary_dark: v })} />
                <ColorField label="Secondary" value={branding.secondary} onChange={(v) => setBranding({ ...branding, secondary: v })} />
                <ColorField label="Accent" value={branding.accent} onChange={(v) => setBranding({ ...branding, accent: v })} />
                <ColorField label="Page background" value={branding.bg_light} onChange={(v) => setBranding({ ...branding, bg_light: v })} />
                <ColorField label="Card background" value={branding.bg_card} onChange={(v) => setBranding({ ...branding, bg_card: v })} />
                <ColorField label="Text color" value={branding.text_color} onChange={(v) => setBranding({ ...branding, text_color: v })} />
              </div>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">Typography</p>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Font family</span>
                <select
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.font_family}
                  onChange={(e) => setBranding({ ...branding, font_family: e.target.value })}
                >
                  {(fonts.length ? fonts : [branding.font_family]).map((f) => (
                    <option key={f} value={f} style={{ fontFamily: f }}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Custom font stack</span>
                <input
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.font_family}
                  onChange={(e) => setBranding({ ...branding, font_family: e.target.value })}
                />
              </label>
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-xs text-gray-500">Base font size</span>
                  <input
                    className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                    value={branding.font_size_base}
                    onChange={(e) => setBranding({ ...branding, font_size_base: e.target.value })}
                    placeholder="16px"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-xs text-gray-500">Heading scale</span>
                  <input
                    className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                    value={branding.heading_scale}
                    onChange={(e) => setBranding({ ...branding, heading_scale: e.target.value })}
                    placeholder="1.25"
                  />
                </label>
              </div>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">Background images</p>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">App background image URL</span>
                <input
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.background_image_url}
                  onChange={(e) => setBranding({ ...branding, background_image_url: e.target.value })}
                  placeholder="https://… or upload below"
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Background overlay (0–1, higher = more solid)</span>
                <input
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.background_overlay}
                  onChange={(e) => setBranding({ ...branding, background_overlay: e.target.value })}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Upload app background</span>
                <input
                  type="file"
                  accept="image/*"
                  className="mt-1 block w-full text-sm"
                  onChange={(e) => uploadBg("app", e.target.files?.[0] || null)}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Login background image URL</span>
                <input
                  className="mt-1 w-full border rounded-xl px-3 py-2 text-sm"
                  value={branding.login_background_url}
                  onChange={(e) => setBranding({ ...branding, login_background_url: e.target.value })}
                />
              </label>
              <label className="block text-sm">
                <span className="text-xs text-gray-500">Upload login background</span>
                <input
                  type="file"
                  accept="image/*"
                  className="mt-1 block w-full text-sm"
                  onChange={(e) => uploadBg("login", e.target.files?.[0] || null)}
                />
              </label>
            </div>

            <div className="rounded-2xl border border-gray-100 p-5" style={previewStyle}>
              <p className="text-xs uppercase tracking-wide opacity-70 mb-2">Live preview</p>
              <h2 className="font-bold" style={{ fontSize: `calc(${branding.font_size_base} * ${branding.heading_scale})`, color: branding.primary }}>
                {branding.app_name}
              </h2>
              <p className="mt-1">Sample body text with your font and colors.</p>
              <button
                type="button"
                className="mt-3 px-4 py-2 rounded-xl text-white text-sm"
                style={{ backgroundColor: branding.primary }}
              >
                Primary button
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={savingBrand}
                className="px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-medium disabled:opacity-60"
              >
                {savingBrand ? "Saving…" : "Save branding"}
              </button>
              <button
                type="button"
                onClick={resetBranding}
                disabled={savingBrand}
                className="px-5 py-2.5 rounded-xl border text-sm"
              >
                Reset defaults
              </button>
            </div>
          </form>
        )}

        {tab === "marquee" && (
          <div className="space-y-6">
            {msg && <p className="text-sm text-emerald-700">{msg}</p>}
            <form onSubmit={submitMarquee} className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
              <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                {editing ? `Edit item #${editing.id}` : "Add marquee item"}
              </p>
              <div>
                <p className="text-xs text-gray-500 mb-2">Icon</p>
                <div className="flex flex-wrap gap-2 mb-2">
                  {icons.map((ic) => (
                    <button
                      key={ic}
                      type="button"
                      onClick={() => setForm({ ...form, icon: ic })}
                      className={`w-10 h-10 rounded-xl border text-lg ${
                        form.icon === ic ? "border-primary bg-primary/10" : "border-gray-200 bg-white"
                      }`}
                    >
                      {ic}
                    </button>
                  ))}
                </div>
                <input
                  className="w-full border rounded-xl px-3 py-2 text-sm"
                  value={form.icon}
                  onChange={(e) => setForm({ ...form, icon: e.target.value })}
                  maxLength={8}
                />
              </div>
              <textarea
                required
                className="w-full border rounded-xl px-3 py-2 text-sm"
                rows={3}
                placeholder="Description shown in the scrolling marquee"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm({ ...form, active: e.target.checked })}
                />
                Active
              </label>
              <div className="flex gap-2">
                <button type="submit" className="flex-1 py-2.5 rounded-xl bg-primary text-white text-sm font-medium">
                  {editing ? "Save changes" : "Add to marquee"}
                </button>
                {editing && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(null);
                      setForm({ icon: "📢", description: "", active: true });
                    }}
                    className="px-4 py-2.5 rounded-xl border text-sm"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>

            <div className="space-y-3">
              {items.map((n) => (
                <article key={n.id} className="rounded-2xl border border-gray-100 bg-white p-4 flex gap-3 items-start">
                  <span className="text-2xl leading-none">{n.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800">{n.description}</p>
                    <p className="text-[11px] text-gray-400 mt-1">{n.active ? "Active" : "Hidden"}</p>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(n);
                        setForm({ icon: n.icon, description: n.description, active: n.active });
                      }}
                      className="text-xs text-primary underline"
                    >
                      Edit
                    </button>
                    <button type="button" onClick={() => removeMarquee(n.id)} className="text-xs text-red-600 underline">
                      Delete
                    </button>
                  </div>
                </article>
              ))}
              {!items.length && <p className="text-sm text-gray-400">No marquee items yet.</p>}
            </div>
          </div>
        )}
      </div>
    </CopilotShell>
  );
}

export default function AdminCmsPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading CMS…</div>}>
        <CmsInner />
      </Suspense>
    </RequireAuth>
  );
}
