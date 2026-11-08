"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";

type Perm = { key: string; label: string; status: string; purpose: string };
type Group = { id: string; label: string; purpose: string; permissions: Perm[] };
type Log = { id: number; when: string; data: string; purpose: string; component: string; permission: string };

function PrivacyInner() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [notice, setNotice] = useState("");
  const [logs, setLogs] = useState<Log[]>([]);

  const load = () => {
    apiGet<{ groups: Group[]; notice: string }>("/api/privacy/consents").then((d) => {
      setGroups(d.groups || []);
      setNotice(d.notice || "");
    });
    apiGet<{ items: Log[] }>("/api/privacy/access-log").then((d) => setLogs(d.items || [])).catch(() => setLogs([]));
  };

  useEffect(() => { load(); }, []);

  const setStatus = async (key: string, status: string) => {
    await apiPost("/api/privacy/consents", { key, status });
    load();
  };

  return (
    <CopilotShell title="Privacy">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">Campus-GPT Consent</h1>
        <p className="text-sm text-gray-600 mt-2">{notice}</p>
        <p className="text-xs text-gray-500 mt-1">
          Deny / revoke any permission and Campus-GPT stops using that data immediately (synced to UIS when linked).
          Turn off Campus-GPT Consent (assist) to disable all personalized help; general campus FAQ still works.
        </p>
        <div className="mt-6 space-y-6">
          {groups.map((g) => (
            <section key={g.id} className="rounded-2xl border border-gray-100 bg-white p-4">
              <h2 className="font-semibold text-primary">{g.label}</h2>
              <p className="text-xs text-gray-500 mt-1">{g.purpose}</p>
              <ul className="mt-3 space-y-2">
                {g.permissions.map((p) => (
                  <li key={p.key} className="flex items-center justify-between gap-3 text-sm">
                    <span>
                      {p.label}
                      <span className="block text-[11px] text-gray-400">{p.status === "allow" ? "Allowed" : "Denied / revoked"}</span>
                    </span>
                    <span className="flex gap-1">
                      <button onClick={() => setStatus(p.key, "allow")} className={`px-2 py-1 rounded-lg text-xs ${p.status === "allow" ? "bg-primary text-white" : "bg-gray-100"}`}>Allow</button>
                      <button onClick={() => setStatus(p.key, "deny")} className={`px-2 py-1 rounded-lg text-xs ${p.status === "deny" ? "bg-red-600 text-white" : "bg-gray-100"}`}>Deny / Revoke</button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <h2 className="text-lg font-semibold text-primary mt-8">Access history</h2>
        <div className="mt-3 space-y-2">
          {logs.length === 0 && <p className="text-sm text-gray-500">No access events yet.</p>}
          {logs.map((l) => (
            <p key={l.id} className="text-sm text-gray-700 rounded-xl border border-gray-100 px-3 py-2">
              {l.when?.slice(0, 16).replace("T", " ")} — {l.data} accessed — Purpose: {l.purpose}
            </p>
          ))}
        </div>
      </main>
    </CopilotShell>
  );
}

export default function PrivacyPage() {
  return <RequireAuth><PrivacyInner /></RequireAuth>;
}
