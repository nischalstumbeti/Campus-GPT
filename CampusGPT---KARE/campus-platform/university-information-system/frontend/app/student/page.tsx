"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Dash = {
  welcome: string;
  name: string;
  program: string;
  year: number;
  semester: number;
  section: string;
  batch: string;
  student_id: string;
  cgpa: number;
  attendance: number;
  credits: string;
  backlogs: number;
  photo_url: string;
};

type Notice = { id: number; title: string; body: string };

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = (parts[0]?.[0] || "S") + (parts[1]?.[0] || "");
  return letters.toUpperCase();
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <tr className="border-b border-slate-200 last:border-0">
      <th className="w-[46%] px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">{label}</th>
      <td className="px-3 py-2 text-sm text-slate-800">{value === "" || value === null || value === undefined ? "—" : value}</td>
    </tr>
  );
}

export default function StudentDashboard() {
  const [data, setData] = useState<Dash | null>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [forms, setForms] = useState<{ id: number; title: string; remaining: number | null }[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<Dash>("/api/v1/student/dashboard")
      .then(setData)
      .catch((e) => setErr(e.message));
    apiFetch<{ items: Notice[] }>("/api/v1/student/announcements")
      .then((d) => setNotices(d.items || []))
      .catch(() => setNotices([]));
    apiFetch<{ items: { id: number; title: string; remaining: number | null }[] }>("/api/v1/forms/open")
      .then((d) => setForms(d.items || []))
      .catch(() => setForms([]));
  }, []);

  return (
    <AppShell>
      {err && <p className="text-red-600 text-sm mb-3">{err}</p>}
      {data && (
        <div className="space-y-4">
          <section className="uis-panel">
            <h1 className="uis-panel-title">Personal Details</h1>
            <div className="grid lg:grid-cols-[150px_1fr_1fr]">
              <div className="p-4 border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col items-center">
                {data.photo_url ? (
                  <img
                    src={data.photo_url}
                    alt={`${data.name} photo`}
                    className="h-40 w-32 object-cover border border-slate-300 bg-slate-100"
                  />
                ) : (
                  <div
                    className="h-40 w-32 border border-slate-300 bg-slate-100 text-brand flex items-center justify-center text-3xl font-semibold"
                    aria-label={`${data.name} photo placeholder`}
                  >
                    {initials(data.name)}
                  </div>
                )}
              </div>
              <table className="w-full border-b lg:border-b-0 lg:border-r border-slate-200">
                <tbody>
                  <Row label="Register Number" value={data.student_id} />
                  <Row label="Name of the Student" value={data.name} />
                  <Row label="Degree / Programme" value={data.program} />
                  <Row label="Batch" value={data.batch} />
                  <Row label="Section" value={data.section} />
                </tbody>
              </table>
              <table className="w-full">
                <tbody>
                  <Row label="Year" value={data.year} />
                  <Row label="Semester" value={data.semester} />
                  <Row label="CGPA" value={data.cgpa} />
                  <Row label="Attendance" value={`${data.attendance}%`} />
                  <Row label="Credits" value={data.credits} />
                  <Row label="Backlogs" value={data.backlogs} />
                </tbody>
              </table>
            </div>
          </section>

          <section className="uis-panel">
            <h2 className="uis-panel-title">Forms</h2>
            {forms.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No form is shared with you.</p>
            ) : (
              <ul>
                {forms.map((form) => (
                  <li key={form.id} className="px-4 py-2 text-sm border-b border-slate-200 last:border-0">
                    <a className="font-medium text-[#0B2A4A] underline" href="/student/forms">{form.title}</a>
                    <span className="text-slate-600"> — {form.remaining === null ? "open" : form.remaining === 0 ? "submitted" : `${form.remaining} left`}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="uis-panel">
            <h2 className="uis-panel-title">Student Notifications</h2>
            {notices.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No student notifications.</p>
            ) : (
              <ul>
                {notices.slice(0, 6).map((n) => (
                  <li key={n.id} className="px-4 py-2 text-sm border-b border-slate-200 last:border-0">
                    <span className="font-medium">{n.title}</span>
                    {n.body ? <span className="text-slate-600"> — {n.body}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
