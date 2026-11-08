"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

export default function AchievementsPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    apiFetch("/api/v1/student/achievements").then(setData);
  }, []);
  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-4">Achievements</h1>
      <ul className="space-y-2">
        {(data?.achievements || []).map((a: any, i: number) => (
          <li key={i} className="bg-white border rounded-lg p-4">
            <p className="font-medium text-brand">{a.title}</p>
            <p className="text-xs text-slate-500 capitalize mt-1">
              {a.category}
              {a.awarded_on ? ` · ${a.awarded_on}` : ""}
            </p>
            <p className="text-sm text-slate-600 mt-2">{a.description}</p>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
