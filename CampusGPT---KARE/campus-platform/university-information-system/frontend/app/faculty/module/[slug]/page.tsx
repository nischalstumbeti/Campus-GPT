"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

const TITLES: Record<string, { title: string; note: string }> = {
  "exam-pattern": {
    title: "Exam Pattern",
    note: "Assessment pattern for the courses assigned to you. Enter the marks from Marks.",
  },
  "lab-timetable": {
    title: "My Class Time Table",
    note: "Open My Class Time Table for the weekly schedule of your allocated classes.",
  },
  biometric: {
    title: "Attendance",
    note: "Attendance for your classes is entered from Attendance. Only students enrolled in that class are listed.",
  },
  "old-results": {
    title: "Old Results",
    note: "Open a student profile to see posted marks, grades, and attendance for your courses.",
  },
  "question-manual": {
    title: "Question Manual",
    note: "Question papers for your courses are published to students from Exam Papers.",
  },
  "question-bank": {
    title: "Question Bank",
    note: "Use your assigned courses below when preparing questions for those classes.",
  },
};

type ClassItem = { offering_id: number; code: string; title: string; section: string; semester: number };

export default function FacultyModulePage() {
  const params = useParams();
  const slug = String(params.slug || "");
  const copy = TITLES[slug] || { title: "Faculty", note: "This section uses the classes assigned to you." };
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ classes: ClassItem[] }>("/api/v1/faculty/classes")
      .then((d) => setClasses(d.classes || []))
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">{copy.title}</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">{copy.note}</p>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Course</th>
              <th className="px-3 py-2">Section</th>
              <th className="px-3 py-2">Semester</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((item) => (
              <tr key={item.offering_id} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">{item.code}</td>
                <td className="px-3 py-2">{item.title}</td>
                <td className="px-3 py-2">{item.section}</td>
                <td className="px-3 py-2">{item.semester}</td>
              </tr>
            ))}
            {!classes.length && !err ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-slate-500">No classes are assigned to you.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className="px-4 py-3 flex flex-wrap gap-3 text-sm">
          <Link href="/faculty/attendance" className="text-brand font-medium">Attendance</Link>
          <Link href="/faculty/marks" className="text-brand font-medium">Marks</Link>
          <Link href="/faculty/students" className="text-brand font-medium">Student profiles</Link>
        </div>
      </section>
    </AppShell>
  );
}
