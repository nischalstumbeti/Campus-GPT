"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Achievement = {
  id: number;
  title: string;
  category: string;
  description: string;
  awarded_on?: string | null;
};

const CATEGORIES = ["award", "certification", "competition", "internship", "publication", "sports", "other"];

export default function FacultyStudentProfilePage() {
  const params = useParams();
  const studentId = String(params.studentId || "");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "",
    category: "award",
    description: "",
    awarded_on: new Date().toISOString().slice(0, 10),
  });
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = () => {
    if (!studentId) return;
    apiFetch(`/api/v1/faculty/students/${studentId}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  };

  useEffect(() => {
    load();
  }, [studentId]);

  const p = data?.profile;
  const achievements: Achievement[] = data?.achievements || [];

  const resetForm = () => {
    setEditingId(null);
    setForm({
      title: "",
      category: "award",
      description: "",
      awarded_on: new Date().toISOString().slice(0, 10),
    });
  };

  const startEdit = (a: Achievement) => {
    setEditingId(a.id);
    setForm({
      title: a.title,
      category: a.category || "award",
      description: a.description || "",
      awarded_on: a.awarded_on || new Date().toISOString().slice(0, 10),
    });
  };

  const saveAchievement = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    setError("");
    try {
      if (editingId) {
        const res = await apiFetch<{ message?: string }>(
          `/api/v1/faculty/students/${studentId}/achievements/${editingId}`,
          { method: "PATCH", body: JSON.stringify(form) }
        );
        setMsg(res.message || "Updated. Student can review it in Student login → Achievements.");
      } else {
        const res = await apiFetch<{ message?: string }>(`/api/v1/faculty/students/${studentId}/achievements`, {
          method: "POST",
          body: JSON.stringify(form),
        });
        setMsg(res.message || "Saved. Student was notified to open Student login.");
      }
      resetForm();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link href="/faculty/students" className="text-[#0B2A4A] underline">
          ← All students
        </Link>
        <Link href="/faculty/classes" className="text-slate-500 underline">
          Classes
        </Link>
      </div>
      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {msg && (
        <p className="text-sm text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2 mb-3">
          {msg}
        </p>
      )}
      {!data && !error && <p className="text-sm text-slate-500">Loading student profile…</p>}
      {p && (
        <>
          <section className="uis-panel mb-6">
            <h1 className="uis-panel-title">Personal Details</h1>
            <div className="grid lg:grid-cols-[150px_1fr_1fr]">
              <div className="p-4 border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col items-center">
                {p.photo_url ? (
                  <img src={p.photo_url} alt="" className="h-40 w-32 object-cover border border-slate-300 bg-slate-100" />
                ) : (
                  <div className="h-40 w-32 border border-slate-300 bg-slate-100 text-brand flex items-center justify-center text-3xl font-semibold">
                    {(p.name || "S").slice(0, 1)}
                  </div>
                )}
              </div>
              <table className="w-full border-b lg:border-b-0 lg:border-r border-slate-200">
                <tbody>
                  <tr className="border-b border-slate-200"><th className="w-[46%] px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Register Number</th><td className="px-3 py-2 text-sm">{p.student_id}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Name of the Student</th><td className="px-3 py-2 text-sm">{p.name}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Degree / Programme</th><td className="px-3 py-2 text-sm">{p.program}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Batch</th><td className="px-3 py-2 text-sm">{p.batch}</td></tr>
                  <tr><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Section</th><td className="px-3 py-2 text-sm">{p.section}</td></tr>
                </tbody>
              </table>
              <table className="w-full">
                <tbody>
                  <tr className="border-b border-slate-200"><th className="w-[46%] px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Year</th><td className="px-3 py-2 text-sm">{p.year}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Semester</th><td className="px-3 py-2 text-sm">{p.semester}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">CGPA</th><td className="px-3 py-2 text-sm">{p.cgpa}</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Attendance</th><td className="px-3 py-2 text-sm">{p.overall_attendance}%</td></tr>
                  <tr className="border-b border-slate-200"><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Credits</th><td className="px-3 py-2 text-sm">{p.credits_completed}/{p.credits_required}</td></tr>
                  <tr><th className="px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">Backlogs</th><td className="px-3 py-2 text-sm">{p.backlogs}</td></tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-white border rounded-xl p-4 shadow-sm mb-6">
            <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
              <div>
                <h2 className="text-sm font-semibold text-[#0B2A4A]">Student achievements</h2>
                <p className="text-xs text-slate-500">
                  Add or update awards for this student. They are notified to review only in{" "}
                  <strong>Student login → Achievements</strong>.
                </p>
              </div>
              <span className="text-[11px] px-2 py-1 rounded border bg-slate-50 text-slate-600">
                Redirect target: student login only
              </span>
            </div>

            <ul className="divide-y border rounded-lg mb-4">
              {achievements.map((a) => (
                <li key={a.id} className="px-3 py-2 text-sm flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-[#0B2A4A]">{a.title}</p>
                    <p className="text-xs text-slate-500 capitalize">
                      {a.category}
                      {a.awarded_on ? ` · ${a.awarded_on}` : ""}
                    </p>
                    {a.description && <p className="text-xs text-slate-600 mt-1 whitespace-pre-wrap">{a.description}</p>}
                  </div>
                  <button type="button" className="text-xs font-semibold text-[#0B2A4A]" onClick={() => startEdit(a)}>
                    Edit
                  </button>
                </li>
              ))}
              {!achievements.length && (
                <li className="px-3 py-4 text-sm text-slate-400 text-center">No achievements on record yet.</li>
              )}
            </ul>

            <form onSubmit={saveAchievement} className="grid sm:grid-cols-2 gap-3 text-sm border-t pt-3">
              <p className="sm:col-span-2 text-xs font-semibold text-[#0B2A4A]">
                {editingId ? `Edit achievement #${editingId}` : "Add achievement"}
              </p>
              <label className="block sm:col-span-2">
                <span className="text-xs text-slate-500">Title</span>
                <input
                  required
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="e.g. Best Project Award — Hackathon 2026"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Category</span>
                <select
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Awarded on</span>
                <input
                  type="date"
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.awarded_on}
                  onChange={(e) => setForm({ ...form, awarded_on: e.target.value })}
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs text-slate-500">Description (optional)</span>
                <textarea
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Short note for the student record"
                />
              </label>
              <div className="sm:col-span-2 flex flex-wrap gap-2">
                <button type="submit" disabled={busy} className="px-4 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm disabled:opacity-50">
                  {editingId ? "Save changes" : "Add achievement"}
                </button>
                {editingId && (
                  <button type="button" className="px-4 py-2 rounded-lg border text-sm" onClick={resetForm}>
                    Cancel edit
                  </button>
                )}
              </div>
            </form>
          </section>

          <div className="bg-white border rounded-xl p-4 shadow-sm mb-6 max-w-xl">
            <h2 className="text-sm font-semibold mb-2">Profile</h2>
            <dl className="text-sm space-y-1">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Email</dt>
                <dd>{p.email}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Year</dt>
                <dd>{p.year}</dd>
              </div>
            </dl>
            {data.hostel ? (
              <div className="mt-4 pt-3 border-t text-sm">
                <p className="font-medium mb-1">Hostel allocation</p>
                <p>
                  {data.hostel.hostel} · {data.hostel.block} · Room {data.hostel.room} (Bed {data.hostel.bed})
                </p>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-400">Day scholar / no hostel allocation</p>
            )}
          </div>

          <section className="uis-panel">
            <h2 className="uis-panel-title">Courses, marks, and attendance</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="uis-table-head text-left">
                  <tr>
                    <th className="px-3 py-2">S.No</th>
                    <th className="px-3 py-2">Code</th>
                    <th className="px-3 py-2">Course</th>
                    <th className="px-3 py-2">Section</th>
                    <th className="px-3 py-2">Faculty</th>
                    <th className="px-3 py-2">Attendance</th>
                    <th className="px-3 py-2">Marks</th>
                    <th className="px-3 py-2">Grade</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.courses || []).map((c: any, index: number) => (
                    <tr key={c.code} className="border-t border-slate-100 align-top">
                      <td className="px-3 py-2">{index + 1}</td>
                      <td className="px-3 py-2 font-medium">{c.code}</td>
                      <td className="px-3 py-2">{c.title}</td>
                      <td className="px-3 py-2">{c.section}</td>
                      <td className="px-3 py-2">{c.faculty}</td>
                      <td className="px-3 py-2">
                        {c.attendance.percentage}% ({c.attendance.attended}/{c.attendance.total})
                      </td>
                      <td className="px-3 py-2">
                        {(c.marks || []).map((m: any) => `${m.assessment} ${m.score}/${m.max_score}`).join(", ") || "—"}
                      </td>
                      <td className="px-3 py-2">{c.grade?.letter || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
