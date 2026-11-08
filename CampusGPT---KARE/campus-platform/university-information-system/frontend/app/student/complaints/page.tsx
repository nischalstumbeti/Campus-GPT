"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Complaint = {
  id: number;
  category: string;
  audience: string;
  subject: string;
  description: string;
  status: string;
  resolution_note: string;
  resolver_username?: string | null;
  resolver_role?: string | null;
  created_at?: string;
};

const CATEGORIES = [
  { value: "hostel", label: "Hostel / room" },
  { value: "mess", label: "Mess / food" },
  { value: "facility", label: "Campus facility" },
  { value: "academic", label: "Academic" },
  { value: "marks", label: "Marks / grades" },
  { value: "attendance", label: "Attendance" },
  { value: "faculty", label: "Faculty related" },
  { value: "general", label: "General" },
  { value: "other", label: "Other" },
];

export default function StudentComplaintsPage() {
  const [rows, setRows] = useState<Complaint[]>([]);
  const [category, setCategory] = useState("general");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [msg, setMsg] = useState("");

  const load = () =>
    apiFetch<{ complaints: Complaint[] }>("/api/v1/complaints/mine")
      .then((d) => setRows(d.complaints || []))
      .catch(() => setRows([]));

  useEffect(() => {
    load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      await apiFetch("/api/v1/complaints", {
        method: "POST",
        body: JSON.stringify({ category, subject, description }),
      });
      setSubject("");
      setDescription("");
      setMsg("Complaint submitted. Faculty / warden / admin can review and resolve it.");
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not submit");
    }
  };

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-[#0B2A4A] mb-1">Raise a complaint</h1>
      <p className="text-sm text-slate-500 mb-4">
        Hostel issues go to the warden; academic issues to faculty. General complaints can be handled by either.
      </p>

      <form onSubmit={submit} className="bg-white border rounded-xl p-4 mb-6 grid gap-2 max-w-xl shadow-sm">
        <label className="text-xs text-slate-500">Category</label>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          required
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Subject"
          className="border rounded-lg px-3 py-2 text-sm"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the issue"
          rows={4}
          className="border rounded-lg px-3 py-2 text-sm"
        />
        <button type="submit" className="w-fit bg-brand text-white rounded-lg px-4 py-2 text-sm font-medium">
          Submit complaint
        </button>
        {msg && <p className="text-sm text-emerald-700">{msg}</p>}
      </form>

      <h2 className="text-sm font-semibold mb-2">My complaints</h2>
      <div className="space-y-3">
        {rows.map((c) => (
          <div key={c.id} className="bg-white border rounded-xl p-4 shadow-sm text-sm">
            <div className="flex flex-wrap justify-between gap-2 mb-1">
              <p className="font-medium text-[#0B2A4A]">{c.subject}</p>
              <span
                className={`capitalize text-xs font-medium ${
                  c.status === "resolved" || c.status === "closed"
                    ? "text-emerald-700"
                    : c.status === "in_progress"
                      ? "text-blue-700"
                      : "text-amber-700"
                }`}
              >
                {c.status.replace("_", " ")}
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-1 capitalize">
              {c.category} · routed to {c.audience}
            </p>
            {c.description && <p className="text-slate-600 mb-2">{c.description}</p>}
            {c.resolution_note && (
              <p className="text-xs bg-slate-50 border rounded-lg px-3 py-2">
                Resolution ({c.resolver_role || "staff"}
                {c.resolver_username ? ` · ${c.resolver_username}` : ""}): {c.resolution_note}
              </p>
            )}
          </div>
        ))}
        {!rows.length && <p className="text-sm text-slate-400">No complaints yet</p>}
      </div>
    </AppShell>
  );
}
