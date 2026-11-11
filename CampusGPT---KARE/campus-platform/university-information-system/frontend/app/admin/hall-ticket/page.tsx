"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Design = {
  enabled: boolean;
  institution: string;
  title: string;
  session_name: string;
  instructions: string;
  footer: string;
  min_attendance: number;
  require_overall: boolean;
  require_subject: boolean;
};

const EMPTY: Design = {
  enabled: false,
  institution: "Campus Information System",
  title: "Hall Ticket",
  session_name: "",
  instructions: "",
  footer: "",
  min_attendance: 75,
  require_overall: true,
  require_subject: true,
};

export default function AdminHallTicketPage() {
  const [form, setForm] = useState<Design>(EMPTY);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    apiFetch<Design>("/api/v1/admin/hall-ticket")
      .then(setForm)
      .catch((e) => setErr(e.message));
  }, []);

  const save = async () => {
    setErr("");
    setMsg("");
    try {
      await apiFetch("/api/v1/admin/hall-ticket", { method: "PUT", body: JSON.stringify(form) });
      setMsg(form.enabled ? "Hall ticket enabled. Students can view, print, and download it." : "Hall ticket closed.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    }
  };

  const set = (patch: Partial<Design>) => setForm((current) => ({ ...current, ...patch }));

  return (
    <AppShell>
      <section className="uis-panel max-w-3xl">
        <h1 className="uis-panel-title">Hall ticket</h1>
        <div className="p-4 space-y-3">
          <p className="text-sm text-slate-600">
            Design the hall ticket here. Students see their own examination schedule, and they can open the PDF only while this is enabled. Change a date, time, or venue from{" "}
            <Link href="/admin/records?tab=exams" className="font-medium text-[#0B2A4A] underline">Timetable & exams</Link>.
          </p>
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-brand">{msg}</p> : null}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
            Enable hall ticket for students
          </label>
          <div className="border rounded-lg p-3 space-y-2">
            <p className="text-sm font-medium text-[#0B2A4A]">Attendance rule</p>
            <p className="text-xs text-slate-500">
              A subject is printed on the hall ticket only when attendance is equal to or above this percentage. Turn on overall, each subject, or both.
            </p>
            <label className="block text-xs text-slate-500">
              Minimum attendance %
              <input
                type="number"
                min={0}
                max={100}
                className="mt-1 w-28 border rounded px-2 py-1 text-sm text-slate-800"
                value={form.min_attendance}
                onChange={(e) => set({ min_attendance: Number(e.target.value) })}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.require_overall} onChange={(e) => set({ require_overall: e.target.checked })} />
              Overall attendance must meet this percentage
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.require_subject} onChange={(e) => set({ require_subject: e.target.checked })} />
              Each subject must meet this percentage
            </label>
          </div>
          <label className="block text-xs text-slate-500">
            Institution
            <input className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={form.institution} onChange={(e) => set({ institution: e.target.value })} />
          </label>
          <label className="block text-xs text-slate-500">
            Title
            <input className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={form.title} onChange={(e) => set({ title: e.target.value })} />
          </label>
          <label className="block text-xs text-slate-500">
            Examination session
            <input className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={form.session_name} onChange={(e) => set({ session_name: e.target.value })} />
          </label>
          <label className="block text-xs text-slate-500">
            Instructions
            <textarea className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" rows={5} value={form.instructions} onChange={(e) => set({ instructions: e.target.value })} />
          </label>
          <label className="block text-xs text-slate-500">
            Footer
            <input className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={form.footer} onChange={(e) => set({ footer: e.target.value })} />
          </label>
          <button type="button" className="px-3 py-1.5 rounded bg-brand text-white text-sm" onClick={save}>
            Save
          </button>
        </div>
      </section>
    </AppShell>
  );
}
