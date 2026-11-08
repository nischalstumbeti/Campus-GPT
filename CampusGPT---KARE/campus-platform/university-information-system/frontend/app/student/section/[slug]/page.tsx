"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import AttendanceBoard, { type AttendanceCourse } from "@/components/AttendanceBoard";
import CourseRegister from "@/components/CourseRegister";
import ExamApply from "@/components/ExamApply";
import HallTicket from "@/components/HallTicket";
import MarksBoard, { type MarkCourse } from "@/components/MarksBoard";
import { apiFetch } from "@/lib/api";

const TITLES: Record<string, string> = {
  revaluation: "Revaluation",
  attendance: "Attendance Details",
  marks: "Marks Details",
  registration: "Registration",
  "hall-ticket": "Hall Ticket",
  "course-registration": "Course Registration",
  "phd-registration": "PhD Course Registration",
  "course-withdrawal": "Course Withdrawal",
  arrear: "Arrear Registration",
  backlog: "Backlog Registration",
  "industrial-training": "Industrial Training TPO",
  "online-courses": "Online Courses",
  "one-credit": "One Credit",
  internships: "Online/Intern/IT Courses",
  "non-cgpa": "NonCGPA",
  makeup: "MakeUp",
  feedback: "Course Feedback",
  "fee-status": "Fee status",
};

type Attendance = { overall: number; courses: AttendanceCourse[] };
type Marks = { courses: MarkCourse[] };
type Academics = { non_cgpa: { code: string; title: string; credits: number; letter: string; semester: number }[] };
type Fee = { id: number; title: string; total_amount: number; paid_amount: number; remaining: number; status: string };

export default function StudentSectionPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const title = TITLES[slug] || "Student section";
  const [attendance, setAttendance] = useState<Attendance | null>(null);
  const [marks, setMarks] = useState<Marks | null>(null);
  const [nonCgpa, setNonCgpa] = useState<Academics["non_cgpa"]>([]);
  const [fees, setFees] = useState<Fee[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr("");
    if (slug === "attendance") {
      apiFetch<Attendance>("/api/v1/student/attendance").then(setAttendance).catch((e) => setErr(e.message));
    } else if (slug === "marks") {
      apiFetch<Marks>("/api/v1/student/marks").then(setMarks).catch((e) => setErr(e.message));
    } else if (slug === "non-cgpa") {
      apiFetch<Academics>("/api/v1/student/academics")
        .then((d) => setNonCgpa(d.non_cgpa || []))
        .catch((e) => setErr(e.message));
    } else if (slug === "fee-status") {
      apiFetch<{ fees: Fee[] }>("/api/v1/fees/mine")
        .then((d) => setFees(d.fees || []))
        .catch((e) => setErr(e.message));
    }
  }, [slug]);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">{title}</h1>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        {(slug === "revaluation" || slug === "arrear" || slug === "backlog") && (
          <ExamApply kind={slug} />
        )}
        {(slug === "registration" || slug === "course-registration") && <CourseRegister kind="registration" />}
        {slug === "course-withdrawal" && <CourseRegister kind="withdrawal" />}
        {slug === "hall-ticket" && <HallTicket />}
        {slug === "attendance" && attendance && <AttendanceBoard courses={attendance.courses || []} />}
        {slug === "marks" && marks && <MarksBoard courses={marks.courses || []} />}
        {slug === "non-cgpa" && (
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left text-xs">
              <tr>
                <th className="px-3 py-2">Semester</th>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Course</th>
                <th className="px-3 py-2">Credits</th>
                <th className="px-3 py-2">Grade</th>
              </tr>
            </thead>
            <tbody>
              {nonCgpa.map((row) => (
                <tr key={row.code} className="border-t border-slate-100">
                  <td className="px-3 py-2">{row.semester}</td>
                  <td className="px-3 py-2">{row.code}</td>
                  <td className="px-3 py-2">{row.title}</td>
                  <td className="px-3 py-2">{row.credits}</td>
                  <td className="px-3 py-2">{row.letter}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {slug === "fee-status" && (
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left text-xs">
              <tr>
                <th className="px-3 py-2">Fee</th>
                <th className="px-3 py-2">Total</th>
                <th className="px-3 py-2">Paid</th>
                <th className="px-3 py-2">Remaining</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {fees.map((row) => (
                <tr key={row.id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{row.title}</td>
                  <td className="px-3 py-2">{row.total_amount}</td>
                  <td className="px-3 py-2">{row.paid_amount}</td>
                  <td className="px-3 py-2">{row.remaining}</td>
                  <td className="px-3 py-2 capitalize">{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {slug !== "attendance" && slug !== "marks" && slug !== "non-cgpa" && slug !== "fee-status" && slug !== "revaluation" && slug !== "arrear" && slug !== "backlog" && slug !== "hall-ticket" && slug !== "registration" && slug !== "course-registration" && slug !== "course-withdrawal" && !err && (
          <p className="px-4 py-4 text-sm text-slate-600">
            {title} is listed in the student menu. Open Grade, Answer Script, or Fees for the records already published for this semester.
          </p>
        )}
      </section>
    </AppShell>
  );
}
