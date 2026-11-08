"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type StudentRow = {
  student_id: string;
  name: string;
  section: string;
  class_code?: string;
};

export default function FacultyStudentsIndex() {
  const [rows, setRows] = useState<StudentRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiFetch<{ students: StudentRow[] }>("/api/v1/faculty/mentees");
        setRows(data.students || []);
      } catch {
        setRows([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const count = useMemo(() => rows.length, [rows]);

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-[#0B2A4A] mb-1">My mentees</h1>
      <p className="text-sm text-slate-500 mb-4">
        Students mapped to you as faculty advisor. Their leave, exam applications, and other requests come to you.
      </p>
      <p className="text-xs text-slate-400 mb-3">{loading ? "Loading…" : `${count} students`}</p>
      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Roll no.</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Section</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.student_id} className="border-t">
                <td className="px-3 py-2 font-medium">{s.student_id}</td>
                <td className="px-3 py-2">{s.name}</td>
                <td className="px-3 py-2">{s.section}</td>
                <td className="px-3 py-2">
                  <Link
                    href={`/faculty/students/${s.student_id}`}
                    className="text-xs font-medium text-[#0B2A4A] underline"
                  >
                    Open profile
                  </Link>
                </td>
              </tr>
            ))}
            {!loading && !rows.length && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-slate-400">
                  No students are mapped to you as faculty advisor
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
