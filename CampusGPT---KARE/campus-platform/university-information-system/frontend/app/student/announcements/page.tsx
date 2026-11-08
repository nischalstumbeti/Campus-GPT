"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

export default function AnnouncementsPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    apiFetch("/api/v1/student/announcements").then(setData);
  }, []);
  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-4">Announcements</h1>
      <ul className="space-y-3">
        {(data?.items || []).map((a: any) => (
          <li key={a.id} className="bg-white border rounded-lg p-4">
            <p className="font-medium text-brand">{a.title}</p>
            <p className="text-xs text-slate-400 mt-1">{a.published_at}</p>
            <p className="text-sm text-slate-600 mt-2 whitespace-pre-wrap">{a.body}</p>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
