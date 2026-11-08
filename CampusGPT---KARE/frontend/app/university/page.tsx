"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { apiGet } from "@/lib/api";

type Item = { id: number; title: string; body: string; category: string; effective_date: string; source: string; important_for_you: boolean };

function UniversityInner() {
  const [items, setItems] = useState<Item[]>([]);
  const [source, setSource] = useState("");
  useEffect(() => {
    apiGet<{ items: Item[]; source?: string }>("/api/copilot/announcements")
      .then((d) => {
        setItems(d.items || []);
        setSource(d.source || "");
      })
      .catch(() => setItems([]));
  }, []);

  return (
    <CopilotShell title="University">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-primary">University updates</h1>
          <SyncBadge source={source} />
        </div>
        <p className="text-sm text-gray-600 mt-1">Official notices from KARE UIS and Campus-GPT — nothing is invented.</p>
        <div className="mt-6 space-y-3">
          {!items.length && <p className="text-sm text-gray-500">No announcements yet.</p>}
          {items.map((n) => (
            <article key={n.id} className="rounded-2xl border border-gray-100 bg-white p-4">
              <div className="flex justify-between gap-2">
                <h2 className="font-semibold text-gray-900">{n.title}</h2>
                {n.important_for_you && <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">Important for you</span>}
              </div>
              <p className="text-xs text-gray-500 mt-1 capitalize">{n.category} · {n.effective_date}</p>
              <p className="text-sm text-gray-700 mt-2">{n.body}</p>
              <p className="text-xs text-primary mt-2">Source: {n.source}</p>
            </article>
          ))}
        </div>
      </main>
    </CopilotShell>
  );
}

export default function UniversityPage() {
  return <RequireAuth><UniversityInner /></RequireAuth>;
}
