"use client";

import { FormEvent, useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost, apiPut } from "@/lib/api";

type Plan = { id: number; title: string; category: string; amount: number; deadline: string; notes: string };
type Row = {
  id: number;
  title: string;
  category: string;
  total_amount: number;
  paid_amount: number;
  remaining: number;
  deadline: string;
  status: string;
  student_name: string;
  student_email: string;
  user_id: number;
};

function FeesAdminInner() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [students, setStudents] = useState<Row[]>([]);
  const [filter, setFilter] = useState("all");
  const [status, setStatus] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [form, setForm] = useState({
    title: "Semester tuition fee",
    category: "hostel",
    amount: "45000",
    deadline: "2026-10-31",
    notes: "",
  });
  const [editDeadline, setEditDeadline] = useState<Record<number, string>>({});

  const load = async () => {
    const [p, s] = await Promise.all([
      apiGet<{ plans: Plan[] }>("/api/fees/plans"),
      apiGet<{ students: Row[] }>(
        `/api/fees/students?category=${filter === "all" ? "" : filter}${status ? `&status=${status}` : ""}`
      ),
    ]);
    setPlans(p.plans || []);
    setStudents(s.students || []);
  };

  useEffect(() => {
    load().catch(() => {
      setPlans([]);
      setStudents([]);
    });
  }, [filter, status]);

  const createPlan = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      const res = await apiPost<{ assigned: number }>("/api/fees/plans", {
        title: form.title,
        category: form.category,
        amount: Number(form.amount),
        deadline: form.deadline,
        notes: form.notes,
        assign_to_students: true,
      });
      setMsg(`Plan created. Assigned to ${res.assigned} student(s).`);
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to create plan");
    }
  };

  const remind = async (category: string, student_user_id?: number) => {
    setMsg("");
    setErr("");
    try {
      const res = await apiPost<{ reminders_sent: number }>("/api/fees/reminders", {
        category,
        student_user_id: student_user_id || null,
        message: "Your fee deadline is approaching. Kindly pay soon.",
      });
      setMsg(`Reminders sent: ${res.reminders_sent}`);
      load();
    } catch {
      setErr("Could not send reminders.");
    }
  };

  const saveDeadline = async (feeId: number) => {
    const deadline = editDeadline[feeId];
    if (!deadline) return;
    await apiPut(`/api/fees/students/${feeId}`, { deadline });
    setMsg("Deadline updated.");
    load();
  };

  return (
    <CopilotShell title="Fee deadlines">
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-primary">Fee deadlines</h1>
          <p className="text-sm text-gray-600">
            Set deadlines for hostel, day scholars, and bus students. Trigger payment reminders.
          </p>
          {err && <p className="text-sm text-red-700 mt-2">{err}</p>}
          {msg && <p className="text-sm text-emerald-700 mt-2">{msg}</p>}
        </div>

        <form onSubmit={createPlan} className="rounded-2xl border border-gray-100 bg-white p-4 grid sm:grid-cols-2 gap-3">
          <input
            className="border rounded-xl px-3 py-2 text-sm"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Title"
            required
          />
          <select
            className="border rounded-xl px-3 py-2 text-sm"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            <option value="all">All students</option>
            <option value="hostel">Hostel</option>
            <option value="day_scholar">Day scholars</option>
            <option value="bus">Bus students</option>
          </select>
          <input
            type="number"
            min={0}
            className="border rounded-xl px-3 py-2 text-sm"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            placeholder="Amount"
            required
          />
          <input
            type="date"
            className="border rounded-xl px-3 py-2 text-sm"
            value={form.deadline}
            onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            required
          />
          <input
            className="border rounded-xl px-3 py-2 text-sm sm:col-span-2"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Notes (optional)"
          />
          <button type="submit" className="sm:col-span-2 py-2.5 rounded-xl bg-primary text-white text-sm font-medium">
            Publish deadline & assign fees
          </button>
        </form>

        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-500">Filter students:</span>
          {["all", "hostel", "day_scholar", "bus"].map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setFilter(c)}
              className={`px-3 py-1 rounded-lg text-xs capitalize ${
                filter === c ? "bg-primary text-white" : "bg-gray-100 text-gray-700"
              }`}
            >
              {c.replace("_", " ")}
            </button>
          ))}
          <select
            className="border rounded-lg px-2 py-1 text-xs"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Any status</option>
            <option value="due">Due</option>
            <option value="partial">Partial</option>
            <option value="overdue">Overdue</option>
            <option value="paid">Paid</option>
          </select>
          <button
            type="button"
            onClick={() => remind(filter)}
            className="ml-auto px-3 py-1.5 rounded-lg bg-amber-500 text-white text-xs font-medium"
          >
            Notify filtered students
          </button>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002"}/api/admin/fees/overdue.csv`}
            className="px-3 py-1.5 rounded-lg border text-xs font-medium"
            onClick={(e) => {
              e.preventDefault();
              const token = localStorage.getItem("campus_gpt_token");
              fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002"}/api/admin/fees/overdue.csv`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              })
                .then((r) => r.blob())
                .then((blob) => {
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "overdue_fees.csv";
                  a.click();
                  URL.revokeObjectURL(url);
                });
            }}
          >
            Export overdue CSV
          </a>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-gray-500 border-b">
              <tr>
                <th className="p-3">Student</th>
                <th className="p-3">Fee</th>
                <th className="p-3">Category</th>
                <th className="p-3">Due</th>
                <th className="p-3">Deadline</th>
                <th className="p-3">Status</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id} className="border-b border-gray-50">
                  <td className="p-3">
                    <p className="font-medium">{s.student_name}</p>
                    <p className="text-xs text-gray-400">{s.student_email}</p>
                  </td>
                  <td className="p-3">{s.title}</td>
                  <td className="p-3 capitalize">{s.category.replace("_", " ")}</td>
                  <td className="p-3">₹{s.remaining}</td>
                  <td className="p-3">
                    <div className="flex gap-1 items-center">
                      <input
                        type="date"
                        className="border rounded px-1 py-0.5 text-xs"
                        value={editDeadline[s.id] ?? s.deadline}
                        onChange={(e) => setEditDeadline((d) => ({ ...d, [s.id]: e.target.value }))}
                      />
                      <button type="button" className="text-xs text-primary underline" onClick={() => saveDeadline(s.id)}>
                        Save
                      </button>
                    </div>
                  </td>
                  <td className="p-3 capitalize">{s.status}</td>
                  <td className="p-3">
                    <button
                      type="button"
                      className="text-xs text-amber-700 underline"
                      onClick={() => remind("all", s.user_id)}
                    >
                      Remind
                    </button>
                  </td>
                </tr>
              ))}
              {!students.length && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-gray-400">
                    No students match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {plans.length > 0 && (
          <div>
            <h2 className="font-semibold text-primary mb-2">Active plans</h2>
            <ul className="text-sm space-y-1 text-gray-600">
              {plans.map((p) => (
                <li key={p.id}>
                  {p.title} · {p.category} · ₹{p.amount} · due {p.deadline}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </CopilotShell>
  );
}

export default function AdminFeesPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <FeesAdminInner />
    </RequireAuth>
  );
}
