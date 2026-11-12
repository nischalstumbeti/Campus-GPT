"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Field = {
  key: string;
  label: string;
  type: "text" | "password" | "number" | "bool";
  placeholder: string;
  required: boolean;
  secret: boolean;
  secret_set: boolean;
  value: string | number | boolean;
};

type Provider = {
  id: string;
  label: string;
  kind: string;
  summary: string;
  configured: boolean;
  fields: Field[];
};

type Catalog = { active: string; providers: Provider[]; ok?: boolean; detail?: string };

function draftFrom(provider: Provider): Record<string, string | boolean> {
  const draft: Record<string, string | boolean> = {};
  provider.fields.forEach((field) => {
    if (field.secret) draft[field.key] = "";
    else if (field.type === "bool") draft[field.key] = Boolean(field.value);
    else draft[field.key] = field.value === undefined || field.value === null ? "" : String(field.value);
  });
  return draft;
}

function valuesFrom(provider: Provider, draft: Record<string, string | boolean>) {
  const values: Record<string, string | number | boolean> = {};
  provider.fields.forEach((field) => {
    const raw = draft[field.key];
    if (field.secret && (raw === undefined || String(raw).trim() === "")) return;
    if (field.type === "bool") values[field.key] = Boolean(raw);
    else if (field.type === "number") values[field.key] = Number(raw || 0);
    else values[field.key] = String(raw ?? "");
  });
  return values;
}

export default function ConnectionsPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selected, setSelected] = useState("supabase");
  const [drafts, setDrafts] = useState<Record<string, Record<string, string | boolean>>>({});
  const [mailTo, setMailTo] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [ok, setOk] = useState(true);

  const applyCatalog = (data: Catalog, keepDraft = true) => {
    setCatalog(data);
    setDrafts((prev) => {
      const next = keepDraft ? { ...prev } : {};
      data.providers.forEach((provider) => {
        if (!next[provider.id]) next[provider.id] = draftFrom(provider);
      });
      return next;
    });
  };

  useEffect(() => {
    apiFetch<Catalog>("/api/v1/admin/integrations")
      .then((data) => {
        applyCatalog(data, false);
        if (data.active) setSelected(data.active);
        const smtp = data.providers.find((p) => p.id === "smtp");
        const user = smtp?.fields.find((f) => f.key === "user")?.value;
        if (typeof user === "string") setMailTo(user);
      })
      .catch((e: Error) => {
        setOk(false);
        setMessage(e.message || "Could not load connectors");
      });
  }, []);

  const stores = useMemo(
    () => (catalog?.providers || []).filter((p) => p.kind === "database" || p.kind === "storage"),
    [catalog]
  );
  const smtp = catalog?.providers.find((p) => p.id === "smtp");
  const current = stores.find((p) => p.id === selected) || stores[0];

  const setField = (providerId: string, key: string, value: string | boolean) => {
    setDrafts((prev) => ({ ...prev, [providerId]: { ...(prev[providerId] || {}), [key]: value } }));
  };

  const run = async (label: string, path: string, method: "POST" | "PUT", body: unknown) => {
    setBusy(label);
    setMessage("");
    try {
      const result = await apiFetch<Catalog>(path, { method, body: JSON.stringify(body) });
      setOk(result.ok !== false);
      setMessage(result.detail || (result.ok === false ? "Failed" : "Done"));
      if (result.providers) applyCatalog(result);
    } catch (e) {
      setOk(false);
      setMessage(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy("");
    }
  };

  const renderFields = (provider: Provider) => (
    <div className="grid gap-3 sm:grid-cols-2">
      {provider.fields.map((field) => {
        const draft = drafts[provider.id] || {};
        if (field.type === "bool") {
          return (
            <label key={field.key} className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={Boolean(draft[field.key])}
                onChange={(e) => setField(provider.id, field.key, e.target.checked)}
              />
              {field.label}
            </label>
          );
        }
        return (
          <label key={field.key} className="block text-sm text-slate-700">
            <span className="font-medium">{field.label}</span>
            {field.secret_set && <span className="ml-2 text-xs text-emerald-700">saved</span>}
            <input
              type={field.type === "password" ? "password" : field.type === "number" ? "number" : "text"}
              value={String(draft[field.key] ?? "")}
              placeholder={field.secret && field.secret_set ? "Leave blank to keep the saved value" : field.placeholder}
              onChange={(e) => setField(provider.id, field.key, e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
        );
      })}
    </div>
  );

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand mb-1">Connections</h1>
      <p className="text-sm text-slate-500 mb-4">
        Choose Supabase, MongoDB, or S3 and test the connection. Change the SMTP host, mailbox, and app password here; email changes apply immediately. The selected store is what other features open. Student records stay on this app’s current database until that URL is changed and the API is restarted.
      </p>

      <section className="bg-white border rounded-lg p-4 mb-4">
        <h2 className="font-semibold text-slate-800">Data store</h2>
        <p className="text-sm text-slate-500 mt-1">
          Active: {catalog?.active ? stores.find((s) => s.id === catalog.active)?.label || catalog.active : "not selected"}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {stores.map((store) => (
            <button
              key={store.id}
              type="button"
              onClick={() => setSelected(store.id)}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                current?.id === store.id ? "bg-brand text-white border-brand" : "border-slate-200 text-slate-700"
              }`}
            >
              {store.label}
              {store.configured ? " · ready" : ""}
            </button>
          ))}
        </div>
        {current && (
          <div className="mt-4 space-y-4">
            <p className="text-sm text-slate-600">{current.summary}</p>
            {renderFields(current)}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!!busy}
                onClick={() =>
                  run("test-store", `/api/v1/admin/integrations/${current.id}/test`, "POST", {
                    values: valuesFrom(current, drafts[current.id] || {}),
                  })
                }
                className="px-4 py-2 rounded-lg border text-sm font-medium disabled:opacity-60"
              >
                {busy === "test-store" ? "Testing…" : "Test connection"}
              </button>
              <button
                type="button"
                disabled={!!busy}
                onClick={() =>
                  run("save-store", `/api/v1/admin/integrations/${current.id}`, "PUT", {
                    values: valuesFrom(current, drafts[current.id] || {}),
                    make_active: true,
                  })
                }
                className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-60"
              >
                {busy === "save-store" ? "Saving…" : "Save and use this store"}
              </button>
            </div>
          </div>
        )}
      </section>

      {smtp && (
        <section className="bg-white border rounded-lg p-4">
          <h2 className="font-semibold text-slate-800">Email service</h2>
          <p className="text-sm text-slate-600 mt-1">{smtp.summary}</p>
          <div className="mt-4 space-y-4">
            {renderFields(smtp)}
            <label className="block text-sm text-slate-700">
              <span className="font-medium">Send test to</span>
              <input
                type="email"
                value={mailTo}
                onChange={(e) => setMailTo(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={!!busy}
                onClick={() =>
                  run("test-mail", "/api/v1/admin/integrations/smtp/test", "POST", {
                    values: valuesFrom(smtp, drafts.smtp || {}),
                    to: mailTo || undefined,
                  })
                }
                className="px-4 py-2 rounded-lg border text-sm font-medium disabled:opacity-60"
              >
                {busy === "test-mail" ? "Testing…" : "Test SMTP"}
              </button>
              <button
                type="button"
                disabled={!!busy}
                onClick={() =>
                  run("save-mail", "/api/v1/admin/integrations/smtp", "PUT", {
                    values: valuesFrom(smtp, drafts.smtp || {}),
                    make_active: false,
                  })
                }
                className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-60"
              >
                {busy === "save-mail" ? "Saving…" : "Save email settings"}
              </button>
            </div>
          </div>
        </section>
      )}

      {message && <p className={`mt-3 text-sm ${ok ? "text-emerald-700" : "text-rose-700"}`}>{message}</p>}
    </AppShell>
  );
}
