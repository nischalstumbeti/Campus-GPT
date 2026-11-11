"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Slip = {
  number: string;
  title: string;
  summary: string;
  email: string;
  email_sent: boolean;
  created_at: string;
};

export default function AcknowledgementListPage() {
  const [items, setItems] = useState<Slip[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ items: Slip[] }>("/api/v1/acknowledgements")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Acknowledgements</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">
          Each number is stored with the record. Email is marked sent only when the mail server accepted it.
        </p>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Number</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">When</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.number} className="border-t">
                <td className="px-3 py-2">
                  <Link className="font-medium text-[#0B2A4A] underline" href={`/ack/${item.number}`}>
                    {item.number}
                  </Link>
                </td>
                <td className="px-3 py-2">{item.title}</td>
                <td className="px-3 py-2">{item.email_sent ? item.email : "Not sent"}</td>
                <td className="px-3 py-2">{item.created_at.replace("T", " ").slice(0, 16)}</td>
              </tr>
            ))}
            {!items.length && !err ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-slate-500">No acknowledgements yet.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
