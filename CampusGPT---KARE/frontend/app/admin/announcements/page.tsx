"use client";

import { FormEvent, useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";

type Item = {
  id: number;
  title: string;
  body: string;
  category: string;
  audience?: string;
  effective_date: string;
  source: string;
};

function AnnouncementsInner() {
  const [items, setItems] = useState<Item[]>([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    title: "",
    body: "",
    category: "general",
    audience: "all",
    department: "",
    effective_date: new Date().toISOString().slice(0, 10),
    important: false,
  });

  const load = () =>
    apiGet<{ items: Item[] }>("/api/copilot/announcements")
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]));

  useEffect(() => {
    load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    try {
      const res = await apiPost<{ cascade: string }>("/api/copilot/announcements", form);
      setMsg(res.cascade || "Announcement published.");
      setForm((f) => ({ ...f, title: "", body: "" }));
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <CopilotShell title="Announcements">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-primary">Upload announcements</h1>
          <p className="text-sm text-gray-600">
            Published notices cascade below admin — to students, faculty, and hostel warden by audience.
          </p>
          {msg && <p className="text-sm text-emerald-700 mt-2">{msg}</p>}
        </div>

        <form onSubmit={submit} className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
          <input
            required
            className="w-full border rounded-xl px-3 py-2 text-sm"
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <textarea
            required
            className="w-full border rounded-xl px-3 py-2 text-sm"
            rows={4}
            placeholder="Describe the announcement"
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
          />
          <div className="grid sm:grid-cols-2 gap-3">
            <select
              className="border rounded-xl px-3 py-2 text-sm"
              value={form.audience}
              onChange={(e) => setForm({ ...form, audience: e.target.value })}
            >
              <option value="all">All (students + faculty + warden)</option>
              <option value="student">Students</option>
              <option value="faculty">Faculty</option>
              <option value="warden">Hostel warden</option>
            </select>
            <select
              className="border rounded-xl px-3 py-2 text-sm"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              <option value="general">General</option>
              <option value="examination">Examination</option>
              <option value="hostel">Hostel</option>
              <option value="department">Department</option>
            </select>
            <input
              type="date"
              className="border rounded-xl px-3 py-2 text-sm"
              value={form.effective_date}
              onChange={(e) => setForm({ ...form, effective_date: e.target.value })}
            />
            <input
              className="border rounded-xl px-3 py-2 text-sm"
              placeholder="Department (optional)"
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={form.important}
              onChange={(e) => setForm({ ...form, important: e.target.checked })}
            />
            Mark as important
          </label>
          <button type="submit" className="w-full py-2.5 rounded-xl bg-primary text-white text-sm font-medium">
            Publish announcement
          </button>
        </form>

        <div className="space-y-3">
          {items.map((n) => (
            <article key={n.id} className="rounded-2xl border border-gray-100 bg-white p-4">
              <div className="flex justify-between gap-2">
                <h2 className="font-semibold">{n.title}</h2>
                <span className="text-[10px] uppercase text-gray-500">{n.audience || "all"}</span>
              </div>
              <p className="text-sm text-gray-700 mt-2">{n.body}</p>
              <p className="text-xs text-primary mt-2">Source: {n.source}</p>
            </article>
          ))}
        </div>
      </div>
    </CopilotShell>
  );
}

export default function AdminAnnouncementsPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <AnnouncementsInner />
    </RequireAuth>
  );
}
