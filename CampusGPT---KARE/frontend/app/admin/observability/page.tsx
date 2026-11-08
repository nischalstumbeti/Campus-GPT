"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";

type Obs = {
  uis_enabled: boolean;
  uis_reachable: boolean;
  uis_announcements: number;
  sync_pending: number;
  sync_failed: number;
  users: number;
  message_threads: number;
  generated_at?: string;
};

function Inner() {
  const [data, setData] = useState<Obs | null>(null);
  const [msg, setMsg] = useState("");

  const load = () =>
    apiGet<Obs>("/api/admin/observability")
      .then(setData)
      .catch(() => setData(null));

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const retry = async () => {
    const res = await apiPost<{ done: number; failed: number }>("/api/admin/sync/retry", {});
    setMsg(`Retry finished · done ${res.done}, failed ${res.failed}`);
    load();
  };

  const resetHint = async () => {
    const res = await apiPost<{ password: string; accounts: string[]; note: string }>("/api/admin/demo/reset-hint", {});
    setMsg(`${res.note} Password: ${res.password}. Accounts: ${res.accounts.join(" · ")}`);
  };

  return (
    <CopilotShell title="Observability">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        <h1 className="text-2xl font-bold text-primary">Observability</h1>
        <p className="text-sm text-gray-600">UIS health, sync queue, and campus activity.</p>
        {msg && <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2">{msg}</p>}
        <div className="grid sm:grid-cols-2 gap-3">
          {[
            ["UIS enabled", data?.uis_enabled ? "Yes" : "No"],
            ["UIS reachable", data?.uis_reachable ? "Up" : "Down / unknown"],
            ["UIS announcements", data?.uis_announcements ?? "—"],
            ["Sync pending", data?.sync_pending ?? "—"],
            ["Sync failed", data?.sync_failed ?? "—"],
            ["Users", data?.users ?? "—"],
            ["Message threads", data?.message_threads ?? "—"],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-2xl border border-gray-100 bg-white p-4">
              <p className="text-xs uppercase text-gray-400">{label}</p>
              <p className="text-xl font-semibold text-primary mt-1">{value as string}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={retry} className="px-4 py-2 rounded-xl bg-primary text-white text-sm">
            Retry failed UIS syncs
          </button>
          <button type="button" onClick={resetHint} className="px-4 py-2 rounded-xl border text-sm">
            Demo reset hint
          </button>
          <button type="button" onClick={load} className="px-4 py-2 rounded-xl border text-sm">
            Refresh
          </button>
        </div>
        <p className="text-[11px] text-gray-400">Updated {data?.generated_at || "—"}</p>
      </div>
    </CopilotShell>
  );
}

export default function ObservabilityPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <Inner />
    </RequireAuth>
  );
}
