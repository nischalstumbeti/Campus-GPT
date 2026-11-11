"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Item = { id: number; title: string; is_open: boolean; public_code: string };

export default function FormResultListPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ items: Item[] }>("/api/v1/forms/results")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Form results</h1>
        <div className="p-4">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          <ul className="divide-y">
            {items.map((item) => (
              <li key={item.id} className="py-3 flex justify-between gap-2">
                <div>
                  <p className="font-medium text-[#0B2A4A]">{item.title}</p>
                  <p className="text-xs text-slate-500">{item.is_open ? "Published" : "Draft"}{item.public_code ? ` · /f/${item.public_code}` : ""}</p>
                </div>
                <Link className="text-sm underline" href={`/forms/results/${item.id}`}>Open</Link>
              </li>
            ))}
            {!items.length && !err ? <li className="py-3 text-sm text-slate-500">No forms are shared with you for results.</li> : null}
          </ul>
        </div>
      </section>
    </AppShell>
  );
}
