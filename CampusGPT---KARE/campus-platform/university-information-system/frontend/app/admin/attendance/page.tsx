"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import AttendanceBoard, { type AttendanceCourse } from "@/components/AttendanceBoard";
import { apiFetch } from "@/lib/api";

type Student = { student_id: string; name: string };

export default function AdminAttendancePage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState("");
  const [courses, setCourses] = useState<AttendanceCourse[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ items: Student[] }>("/api/v1/admin/students?limit=200")
      .then((d) => {
        const rows = d.items || [];
        setStudents(rows);
        if (rows[0]) setStudentId(rows[0].student_id);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const load = async (id: string) => {
    const data = await apiFetch<{ courses: AttendanceCourse[] }>(`/api/v1/admin/students/${id}/attendance`);
    setCourses(data.courses || []);
  };

  useEffect(() => {
    if (!studentId) return;
    setErr("");
    load(studentId).catch((e) => setErr(e.message));
  }, [studentId]);

  const save = async (
    courseCode: string,
    row: { id?: number; entry_date: string; slot_name: string; status: string }
  ) => {
    await apiFetch(`/api/v1/admin/students/${studentId}/attendance`, {
      method: "POST",
      body: JSON.stringify({
        course_code: courseCode,
        entry_date: row.entry_date,
        slot_name: row.slot_name,
        status: row.status,
        session_id: row.id || null,
      }),
    });
    await load(studentId);
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Attendance Details</h1>
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-600">
            Student
            <select className="ml-2 border rounded px-2 py-1" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
              {students.map((student) => (
                <option key={student.student_id} value={student.student_id}>
                  {student.name} · {student.student_id}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-slate-500">Open a course, then add a date, slot, and status. P present, A absent, OD on duty, ML medical, RH holiday, EH extra hours.</p>
        </div>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <AttendanceBoard courses={courses} editable onSave={save} />
      </section>
    </AppShell>
  );
}
