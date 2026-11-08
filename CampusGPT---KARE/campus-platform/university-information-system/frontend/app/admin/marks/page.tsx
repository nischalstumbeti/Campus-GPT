"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import MarksBoard, { type MarkCourse } from "@/components/MarksBoard";
import { apiDownload, apiFetch, apiUpload } from "@/lib/api";

type Student = { student_id: string; name: string };

export default function AdminMarksPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState("");
  const [courses, setCourses] = useState<MarkCourse[]>([]);
  const [err, setErr] = useState("");
  const [csvMsg, setCsvMsg] = useState("");
  const [csvErrors, setCsvErrors] = useState<{ row: number; error: string }[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<{ items: Student[] }>("/api/v1/admin/students?limit=200")
      .then((d) => {
        const rows = d.items || [];
        setStudents(rows);
        if (rows[0]) setStudentId(rows[0].student_id);
      })
      .catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!studentId) return;
    setErr("");
    apiFetch<{ courses: MarkCourse[] }>(`/api/v1/admin/students/${studentId}/marks`)
      .then((d) => setCourses(d.courses || []))
      .catch((e) => setErr(e.message));
  }, [studentId]);

  const reload = async (id = studentId) => {
    if (!id) return;
    const fresh = await apiFetch<{ courses: MarkCourse[] }>(`/api/v1/admin/students/${id}/marks`);
    setCourses(fresh.courses || []);
  };

  const importCsv = async (file: File) => {
    setBusy(true);
    setErr("");
    setCsvMsg("");
    setCsvErrors([]);
    try {
      const result = await apiUpload<{
        message: string;
        errors: { row: number; error: string }[];
      }>("/api/v1/admin/marks/import", file);
      setCsvMsg(result.message);
      setCsvErrors(result.errors || []);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not import the file");
    } finally {
      setBusy(false);
    }
  };

  const save = async (courseCode: string, row: { assessment: string; score: number; max_score: number }) => {
    await apiFetch(`/api/v1/admin/students/${studentId}/marks`, {
      method: "POST",
      body: JSON.stringify({
        course_code: courseCode,
        assessment: row.assessment,
        score: row.score,
        max_score: row.max_score,
      }),
    });
    await reload();
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Marks Details</h1>
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-600">
            Student
            <select
              className="ml-2 border rounded px-2 py-1"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
            >
              {students.map((student) => (
                <option key={student.student_id} value={student.student_id}>
                  {student.name} · {student.student_id}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-slate-500">Open a course, then enter or update each assessment. Or upload a CSV for many students.</p>
          <button
            type="button"
            className="px-3 py-1.5 rounded border text-sm"
            onClick={() => apiDownload("/api/v1/admin/marks/template", "uis_marks_import_template.csv").catch((e) => setErr(e.message))}
          >
            Download CSV template
          </button>
          <label className="text-sm text-slate-600">
            Upload CSV
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm,text/csv"
              disabled={busy}
              className="ml-2 text-sm"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) importCsv(file);
              }}
            />
          </label>
        </div>
        {csvMsg ? <p className="px-4 py-2 text-sm text-brand">{csvMsg}</p> : null}
        {csvErrors.length ? (
          <ul className="px-4 pb-2 text-xs text-red-700 space-y-0.5">
            {csvErrors.map((row) => (
              <li key={`${row.row}-${row.error}`}>Row {row.row}: {row.error}</li>
            ))}
          </ul>
        ) : null}
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <MarksBoard courses={courses} editable onSave={save} />
      </section>
    </AppShell>
  );
}
