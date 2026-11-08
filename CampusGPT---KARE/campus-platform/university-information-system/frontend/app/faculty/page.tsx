"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Profile = {
  name: string;
  email: string;
  faculty_id: string;
  designation: string;
  department: string;
  role: string;
  assigned_offerings: number;
  students_tracked: number;
  pending_student_leaves: number;
  open_complaints: number;
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || "F") + (parts[1]?.[0] || "")).toUpperCase();
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <tr className="border-b border-slate-200 last:border-0">
      <th className="w-[46%] px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">{label}</th>
      <td className="px-3 py-2 text-sm text-slate-800">{value === "" || value === null || value === undefined ? "—" : value}</td>
    </tr>
  );
}

export default function FacultyDashboard() {
  const [data, setData] = useState<Profile | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<Profile>("/api/v1/faculty/dashboard")
      .then(setData)
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      {err ? <p className="text-sm text-red-600 mb-3">{err}</p> : null}
      {data ? (
        <div className="space-y-4">
          <section className="uis-panel">
            <h1 className="uis-panel-title">Personal Details</h1>
            <div className="grid lg:grid-cols-[150px_1fr_1fr]">
              <div className="p-4 border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col items-center">
                <div className="h-40 w-32 border border-slate-300 bg-slate-100 text-brand flex items-center justify-center text-3xl font-semibold">
                  {initials(data.name || "Faculty")}
                </div>
              </div>
              <table className="w-full border-b lg:border-b-0 lg:border-r border-slate-200">
                <tbody>
                  <Row label="Faculty ID" value={data.faculty_id} />
                  <Row label="Name" value={data.name} />
                  <Row label="Designation" value={data.designation} />
                  <Row label="Department" value={data.department} />
                  <Row label="Email" value={data.email} />
                </tbody>
              </table>
              <table className="w-full">
                <tbody>
                  <Row label="Role" value={data.role} />
                  <Row label="Classes" value={data.assigned_offerings} />
                  <Row label="Students" value={data.students_tracked} />
                  <Row label="Pending leave" value={data.pending_student_leaves} />
                  <Row label="Open complaints" value={data.open_complaints} />
                </tbody>
              </table>
            </div>
          </section>
          <div className="flex flex-wrap gap-3">
            <Link href="/faculty/classes" className="rounded-lg bg-brand text-white text-sm font-medium px-4 py-2.5">
              My classes
            </Link>
            <Link href="/faculty/students" className="rounded-lg border border-brand text-brand text-sm font-medium px-4 py-2.5">
              Student profiles
            </Link>
            <Link href="/faculty/attendance" className="rounded-lg border border-brand text-brand text-sm font-medium px-4 py-2.5">
              Attendance
            </Link>
            <Link href="/faculty/marks" className="rounded-lg border border-brand text-brand text-sm font-medium px-4 py-2.5">
              Enter marks
            </Link>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
