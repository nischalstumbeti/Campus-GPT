"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type ClassItem = { offering_id: number; code: string; title: string; section: string; semester: number };
type Student = {
  sno: number;
  student_id: string;
  name: string;
  section: string;
  conducted: number;
  attended: number;
  percentage: number;
};

export default function FacultyClasses() {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selected, setSelected] = useState<ClassItem | null>(null);
  const [students, setStudents] = useState<Student[]>([]);

  useEffect(() => {
    apiFetch<{ classes: ClassItem[] }>("/api/v1/faculty/classes").then((data) => {
      const rows = data.classes || [];
      setClasses(rows);
      if (rows[0]) openClass(rows[0]);
    });
  }, []);

  const openClass = (item: ClassItem) => {
    setSelected(item);
    apiFetch<{ students: Student[] }>(`/api/v1/faculty/classes/${item.offering_id}/students`).then((data) =>
      setStudents(data.students || [])
    );
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Allocated courses</h1>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Course</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Semester</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {classes.map((item) => (
                <tr key={item.offering_id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{item.code}</td>
                  <td className="px-3 py-2">{item.title}</td>
                  <td className="px-3 py-2">{item.section}</td>
                  <td className="px-3 py-2">{item.semester}</td>
                  <td className="px-3 py-2">
                    <button type="button" className="text-[#0B2A4A] font-medium" onClick={() => openClass(item)}>
                      Students
                    </button>
                  </td>
                </tr>
              ))}
              {!classes.length ? (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-slate-500">
                    No course section is allocated to you yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section className="uis-panel mt-4">
        <h2 className="uis-panel-title">
          {selected ? `${selected.code} · ${selected.title} · Section ${selected.section}` : "Course students"}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">S.No</th>
                <th className="px-3 py-2">Register number</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Attended</th>
                <th className="px-3 py-2">Conducted</th>
                <th className="px-3 py-2">%</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => (
                <tr key={student.student_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{student.sno}</td>
                  <td className="px-3 py-2 font-medium">{student.student_id}</td>
                  <td className="px-3 py-2">{student.name}</td>
                  <td className="px-3 py-2">{student.section}</td>
                  <td className="px-3 py-2">{student.attended}</td>
                  <td className="px-3 py-2">{student.conducted}</td>
                  <td className="px-3 py-2">{Number(student.percentage || 0).toFixed(1)}</td>
                  <td className="px-3 py-2">
                    <Link href={`/faculty/students/${student.student_id}`} className="text-[#0B2A4A] font-medium">
                      Profile
                    </Link>
                  </td>
                </tr>
              ))}
              {selected && !students.length ? (
                <tr>
                  <td colSpan={8} className="px-3 py-4 text-slate-500">
                    No students are mapped to this course section.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
