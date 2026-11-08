"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Row = {
  id: number;
  title: string;
  category: string;
  remaining: number;
  deadline: string;
  status: string;
  student_name: string;
  student_email: string;
  user_id: number;
};

export default function AdminFeesPage() {
  const [students, setStudents] = useState<Row[]>([]);
  const [filter, setFilter] = useState("all");
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({
    title: "Semester tuition fee",
    category: "hostel",
    amount: "45000",
    deadline: "2026-10-31",
    notes: "",
  });

  const load = () =>
    apiFetch<{ students: Row[] }>(`/api/v1/fees/students?category=${filter === "all" ? "" : filter}`)
      .then((d) => setStudents(d.students || []))
      .catch(() => setStudents([]));

  useEffect(() => {
    load();
  }, [filter]);

  const createPlan = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiFetch<{ assigned: number }>("/api/v1/fees/plans", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          amount: Number(form.amount),
          assign_to_students: true,
        }),
      });
      setMsg(`Plan published. Assigned to ${res.assigned} students (visible in Campus-GPT too).`);
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  };

  const remind = async () => {
    const res = await apiFetch<{ reminders_sent: number }>("/api/v1/fees/reminders", {
      method: "POST",
      body: JSON.stringify({
        category: filter,
        message: "Your fee deadline is approaching. Kindly pay soon.",
      }),
    });
    setMsg(`Reminders sent: ${res.reminders_sent}`);
  };

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand mb-1">Fee deadlines</h1>
      <p className="text-sm text-slate-600 mb-4">UIS source of truth — same data Campus-GPT students see.</p>
      {msg && <p className="text-sm text-emerald-700 mb-3">{msg}</p>}
      <form onSubmit={createPlan} className="bg-white border border-slate-200 rounded-lg p-4 grid sm:grid-cols-2 gap-3 mb-6">
        <input className="border rounded-md px-3 py-2 text-sm" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
        <select className="border rounded-md px-3 py-2 text-sm" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
          <option value="all">All</option>
          <option value="hostel">Hostel</option>
          <option value="day_scholar">Day scholars</option>
          <option value="bus">Bus</option>
        </select>
        <input type="number" className="border rounded-md px-3 py-2 text-sm" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
        <input type="date" className="border rounded-md px-3 py-2 text-sm" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} required />
        <button type="submit" className="sm:col-span-2 py-2 bg-brand text-white rounded-md text-sm">
          Publish deadline & assign
        </button>
      </form>
      <div className="flex flex-wrap gap-2 mb-3">
        {["all", "hostel", "day_scholar", "bus"].map((c) => (
          <button key={c} type="button" onClick={() => setFilter(c)} className={`px-3 py-1 rounded text-xs capitalize ${filter === c ? "bg-brand text-white" : "bg-slate-100"}`}>
            {c.replace("_", " ")}
          </button>
        ))}
        <button type="button" onClick={remind} className="ml-auto px-3 py-1 rounded text-xs bg-amber-500 text-white">
          Notify filtered students
        </button>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500 border-b">
            <tr>
              <th className="p-3">Student</th>
              <th className="p-3">Fee</th>
              <th className="p-3">Due</th>
              <th className="p-3">Deadline</th>
              <th className="p-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id} className="border-b border-slate-50">
                <td className="p-3">
                  <p className="font-medium">{s.student_name}</p>
                  <p className="text-xs text-slate-400">{s.student_email}</p>
                </td>
                <td className="p-3">{s.title}</td>
                <td className="p-3">₹{s.remaining}</td>
                <td className="p-3">{s.deadline}</td>
                <td className="p-3 capitalize">{s.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
