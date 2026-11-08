"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { apiGet } from "@/lib/api";

function AchievementsInner() {
  const [items, setItems] = useState<{ kind: string; title: string; detail: string; year: string }[]>([]);
  const [source, setSource] = useState("");
  useEffect(() => {
    apiGet<{ items: typeof items; source?: string }>("/api/copilot/achievements")
      .then((d) => {
        setItems(d.items || []);
        setSource(d.source || "");
      })
      .catch(() => setItems([]));
  }, []);

  return (
    <CopilotShell title="Achievements">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-primary">Achievements</h1>
          <SyncBadge source={source} />
        </div>
        <p className="text-sm text-gray-600 mt-1">From KARE UIS when linked. Used for career drafts only if you allow it in Privacy.</p>
        <div className="mt-4 space-y-3">
          {!items.length && <p className="text-sm text-gray-500">No achievements on record yet.</p>}
          {items.map((i, n) => (
            <div key={n} className="rounded-2xl border border-gray-100 bg-white p-4">
              <p className="text-[11px] uppercase text-primary">{i.kind}</p>
              <p className="font-semibold">{i.title}</p>
              <p className="text-sm text-gray-600">{i.detail} {i.year}</p>
            </div>
          ))}
        </div>
      </main>
    </CopilotShell>
  );
}

export default function AchievementsPage() {
  return <RequireAuth roles={["student"]}><AchievementsInner /></RequireAuth>;
}
