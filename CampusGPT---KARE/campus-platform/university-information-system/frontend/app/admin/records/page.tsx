"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Option = { id: number; label?: string; name?: string; code?: string };
type CourseRow = {
  id: number;
  code: string;
  title: string;
  credits: number;
  department_id: number;
  result_group: string;
};
type SlotRow = {
  id: number;
  offering_id: number;
  day: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room: string;
  code: string;
  title: string;
  section: string;
  faculty: string;
};
type ExamRow = {
  id: number;
  course_id: number;
  code: string;
  title: string;
  exam_type: string;
  exam_date: string;
  start_time: string;
  venue: string;
  semester: number;
  paper_text: string;
};
type OfficeRow = {
  id: number;
  faculty_id: number;
  faculty_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  kind: string;
  location: string;
  notes: string;
};
type Bundle = {
  offerings: Option[];
  courses: CourseRow[];
  departments: { id: number; code: string; name: string }[];
  faculty: Option[];
  timetable: SlotRow[];
  exams: ExamRow[];
  office_hours: OfficeRow[];
};

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const TABS = [
  { id: "timetable", label: "Class timetable" },
  { id: "exams", label: "Exam venues" },
  { id: "office", label: "Faculty hours" },
  { id: "courses", label: "Courses" },
];

const emptySlot = { offering_id: "", day_of_week: "0", start_time: "09:00", end_time: "09:50", room: "" };
const emptyExam = { course_id: "", exam_type: "End Semester", exam_date: "", start_time: "09:30", venue: "", semester: "1", paper_text: "" };
const emptyOffice = { faculty_id: "", day_of_week: "Monday", start_time: "15:00", end_time: "16:00", kind: "office_hours", location: "", notes: "" };
const emptyCourse = { code: "", title: "", credits: "3", department_id: "", result_group: "cgpa" };

function RecordsPage() {
  const params = useSearchParams();
  const initial = params.get("tab") || "timetable";
  const [tab, setTab] = useState(TABS.some((item) => item.id === initial) ? initial : "timetable");
  const [data, setData] = useState<Bundle | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [slot, setSlot] = useState(emptySlot);
  const [slotId, setSlotId] = useState<number | null>(null);
  const [exam, setExam] = useState(emptyExam);
  const [examId, setExamId] = useState<number | null>(null);
  const [office, setOffice] = useState(emptyOffice);
  const [officeId, setOfficeId] = useState<number | null>(null);
  const [course, setCourse] = useState(emptyCourse);
  const [courseId, setCourseId] = useState<number | null>(null);

  const load = () =>
    apiFetch<Bundle>("/api/v1/admin/records")
      .then(setData)
      .catch((e) => setErr(e.message));

  useEffect(() => {
    load();
  }, []);

  const run = async (path: string, method: string, body?: unknown) => {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await apiFetch(path, { method, body: body ? JSON.stringify(body) : undefined });
      await load();
      return true;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const saveSlot = async (e: FormEvent) => {
    e.preventDefault();
    const body = {
      offering_id: Number(slot.offering_id),
      day_of_week: Number(slot.day_of_week),
      start_time: slot.start_time,
      end_time: slot.end_time,
      room: slot.room.trim(),
    };
    const ok = await run(slotId ? `/api/v1/admin/records/timetable/${slotId}` : "/api/v1/admin/records/timetable", slotId ? "PATCH" : "POST", body);
    if (ok) {
      setSlot(emptySlot);
      setSlotId(null);
      setMsg(slotId ? "Class period updated." : "Class period added. Students and faculty see it on their timetable.");
    }
  };

  const saveExam = async (e: FormEvent) => {
    e.preventDefault();
    const body = {
      course_id: Number(exam.course_id),
      exam_type: exam.exam_type.trim(),
      exam_date: exam.exam_date,
      start_time: exam.start_time,
      venue: exam.venue.trim(),
      semester: Number(exam.semester),
      paper_text: exam.paper_text,
    };
    const ok = await run(examId ? `/api/v1/admin/records/exams/${examId}` : "/api/v1/admin/records/exams", examId ? "PATCH" : "POST", body);
    if (ok) {
      setExam(emptyExam);
      setExamId(null);
      setMsg(examId ? "Examination updated. The hall ticket uses this venue." : "Examination added.");
    }
  };

  const saveOffice = async (e: FormEvent) => {
    e.preventDefault();
    const body = {
      faculty_id: Number(office.faculty_id),
      day_of_week: office.day_of_week,
      start_time: office.start_time,
      end_time: office.end_time,
      kind: office.kind.trim() || "office_hours",
      location: office.location.trim(),
      notes: office.notes.trim(),
    };
    const ok = await run(
      officeId ? `/api/v1/admin/records/office-hours/${officeId}` : "/api/v1/admin/records/office-hours",
      officeId ? "PATCH" : "POST",
      body
    );
    if (ok) {
      setOffice(emptyOffice);
      setOfficeId(null);
      setMsg(officeId ? "Faculty hours updated." : "Faculty hours added.");
    }
  };

  const saveCourse = async (e: FormEvent) => {
    e.preventDefault();
    const body = {
      code: course.code.trim(),
      title: course.title.trim(),
      credits: Number(course.credits),
      department_id: Number(course.department_id),
      result_group: course.result_group,
    };
    const ok = await run(courseId ? `/api/v1/admin/records/courses/${courseId}` : "/api/v1/admin/records/courses", courseId ? "PATCH" : "POST", body);
    if (ok) {
      setCourse(emptyCourse);
      setCourseId(null);
      setMsg(courseId ? "Course updated." : "Course added. Allocate it before it appears on a timetable.");
    }
  };

  const remove = async (path: string, label: string) => {
    if (!window.confirm(`Delete this ${label}?`)) return;
    const ok = await run(path, "DELETE");
    if (ok) setMsg(`${label[0].toUpperCase()}${label.slice(1)} deleted.`);
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Timetable and examinations</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">
          Add, change, or remove class periods, hall-ticket venues, faculty hours, and courses. Photos for faculty and students are edited from Users.
        </p>
        <div className="px-4 pt-3 flex flex-wrap gap-2">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`px-3 py-1.5 rounded text-sm ${tab === item.id ? "bg-[#0B2A4A] text-white" : "border text-slate-700"}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="p-4 space-y-3">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-brand">{msg}</p> : null}
          {!data ? <p className="text-sm text-slate-500">Loading records…</p> : null}

          {data && tab === "timetable" ? (
            <>
              <form onSubmit={saveSlot} className="grid md:grid-cols-5 gap-2 items-end">
                <label className="md:col-span-2 text-xs text-slate-500">
                  Class
                  <select required className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={slot.offering_id} onChange={(e) => setSlot({ ...slot, offering_id: e.target.value })}>
                    <option value="">Select</option>
                    {data.offerings.map((row) => (
                      <option key={row.id} value={row.id}>{row.label}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Day
                  <select className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={slot.day_of_week} onChange={(e) => setSlot({ ...slot, day_of_week: e.target.value })}>
                    {DAYS.map((name, index) => (
                      <option key={name} value={index}>{name}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Start
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={slot.start_time} onChange={(e) => setSlot({ ...slot, start_time: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  End
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={slot.end_time} onChange={(e) => setSlot({ ...slot, end_time: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Room
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={slot.room} onChange={(e) => setSlot({ ...slot, room: e.target.value })} />
                </label>
                <button disabled={busy} className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-60">{slotId ? "Update period" : "Add period"}</button>
                {slotId ? (
                  <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => { setSlot(emptySlot); setSlotId(null); }}>Cancel</button>
                ) : null}
              </form>
              <RecordTable
                headers={["Day", "Time", "Course", "Section", "Room", "Faculty", ""]}
                rows={data.timetable.map((row) => [
                  row.day,
                  `${row.start_time}–${row.end_time}`,
                  `${row.code} ${row.title}`,
                  row.section,
                  row.room,
                  row.faculty || "—",
                  <RowActions
                    key={row.id}
                    onEdit={() => {
                      setSlotId(row.id);
                      setSlot({ offering_id: String(row.offering_id), day_of_week: String(row.day_of_week), start_time: row.start_time, end_time: row.end_time, room: row.room });
                    }}
                    onDelete={() => remove(`/api/v1/admin/records/timetable/${row.id}`, "class period")}
                  />,
                ])}
              />
            </>
          ) : null}

          {data && tab === "exams" ? (
            <>
              <form onSubmit={saveExam} className="grid md:grid-cols-4 gap-2 items-end">
                <label className="md:col-span-2 text-xs text-slate-500">
                  Course
                  <select required className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={exam.course_id} onChange={(e) => setExam({ ...exam, course_id: e.target.value })}>
                    <option value="">Select</option>
                    {data.courses.map((row) => (
                      <option key={row.id} value={row.id}>{row.code} · {row.title}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Type
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.exam_type} onChange={(e) => setExam({ ...exam, exam_type: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Date
                  <input required type="date" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.exam_date} onChange={(e) => setExam({ ...exam, exam_date: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Start
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.start_time} onChange={(e) => setExam({ ...exam, start_time: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Venue
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.venue} onChange={(e) => setExam({ ...exam, venue: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Semester
                  <input required type="number" min={1} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.semester} onChange={(e) => setExam({ ...exam, semester: e.target.value })} />
                </label>
                <label className="md:col-span-4 text-xs text-slate-500">
                  Paper note
                  <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={exam.paper_text} onChange={(e) => setExam({ ...exam, paper_text: e.target.value })} />
                </label>
                <button disabled={busy} className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-60">{examId ? "Update examination" : "Add examination"}</button>
                {examId ? (
                  <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => { setExam(emptyExam); setExamId(null); }}>Cancel</button>
                ) : null}
              </form>
              <RecordTable
                headers={["Date", "Time", "Course", "Type", "Venue", "Sem", ""]}
                rows={data.exams.map((row) => [
                  row.exam_date,
                  row.start_time,
                  `${row.code} ${row.title}`,
                  row.exam_type,
                  row.venue,
                  String(row.semester),
                  <RowActions
                    key={row.id}
                    onEdit={() => {
                      setExamId(row.id);
                      setExam({
                        course_id: String(row.course_id),
                        exam_type: row.exam_type,
                        exam_date: row.exam_date,
                        start_time: row.start_time,
                        venue: row.venue,
                        semester: String(row.semester),
                        paper_text: row.paper_text,
                      });
                    }}
                    onDelete={() => remove(`/api/v1/admin/records/exams/${row.id}`, "examination")}
                  />,
                ])}
              />
            </>
          ) : null}

          {data && tab === "office" ? (
            <>
              <form onSubmit={saveOffice} className="grid md:grid-cols-4 gap-2 items-end">
                <label className="md:col-span-2 text-xs text-slate-500">
                  Faculty
                  <select required className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={office.faculty_id} onChange={(e) => setOffice({ ...office, faculty_id: e.target.value })}>
                    <option value="">Select</option>
                    {data.faculty.map((row) => (
                      <option key={row.id} value={row.id}>{row.name}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Day
                  <select className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={office.day_of_week} onChange={(e) => setOffice({ ...office, day_of_week: e.target.value })}>
                    {DAYS.map((name) => (
                      <option key={name}>{name}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Kind
                  <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={office.kind} onChange={(e) => setOffice({ ...office, kind: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Start
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={office.start_time} onChange={(e) => setOffice({ ...office, start_time: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  End
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={office.end_time} onChange={(e) => setOffice({ ...office, end_time: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Place
                  <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={office.location} onChange={(e) => setOffice({ ...office, location: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Note
                  <input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={office.notes} onChange={(e) => setOffice({ ...office, notes: e.target.value })} />
                </label>
                <button disabled={busy} className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-60">{officeId ? "Update hours" : "Add hours"}</button>
                {officeId ? (
                  <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => { setOffice(emptyOffice); setOfficeId(null); }}>Cancel</button>
                ) : null}
              </form>
              <RecordTable
                headers={["Faculty", "Day", "Time", "Place", "Note", ""]}
                rows={data.office_hours.map((row) => [
                  row.faculty_name,
                  row.day_of_week,
                  `${row.start_time}–${row.end_time}`,
                  row.location || "—",
                  row.notes || "—",
                  <RowActions
                    key={row.id}
                    onEdit={() => {
                      setOfficeId(row.id);
                      setOffice({
                        faculty_id: String(row.faculty_id),
                        day_of_week: row.day_of_week,
                        start_time: row.start_time,
                        end_time: row.end_time,
                        kind: row.kind,
                        location: row.location,
                        notes: row.notes,
                      });
                    }}
                    onDelete={() => remove(`/api/v1/admin/records/office-hours/${row.id}`, "faculty hours")}
                  />,
                ])}
              />
            </>
          ) : null}

          {data && tab === "courses" ? (
            <>
              <form onSubmit={saveCourse} className="grid md:grid-cols-5 gap-2 items-end">
                <label className="text-xs text-slate-500">
                  Code
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={course.code} onChange={(e) => setCourse({ ...course, code: e.target.value })} />
                </label>
                <label className="md:col-span-2 text-xs text-slate-500">
                  Title
                  <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={course.title} onChange={(e) => setCourse({ ...course, title: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Credits
                  <input required type="number" min={0} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={course.credits} onChange={(e) => setCourse({ ...course, credits: e.target.value })} />
                </label>
                <label className="text-xs text-slate-500">
                  Department
                  <select required className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={course.department_id} onChange={(e) => setCourse({ ...course, department_id: e.target.value })}>
                    <option value="">Select</option>
                    {data.departments.map((row) => (
                      <option key={row.id} value={row.id}>{row.code}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-500">
                  Result group
                  <select className="mt-1 w-full border rounded px-2 py-1 text-sm text-slate-800" value={course.result_group} onChange={(e) => setCourse({ ...course, result_group: e.target.value })}>
                    <option value="cgpa">CGPA</option>
                    <option value="non_cgpa">Non CGPA</option>
                    <option value="mandatory">Mandatory</option>
                  </select>
                </label>
                <button disabled={busy} className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-60">{courseId ? "Update course" : "Add course"}</button>
                {courseId ? (
                  <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => { setCourse(emptyCourse); setCourseId(null); }}>Cancel</button>
                ) : null}
              </form>
              <RecordTable
                headers={["Code", "Title", "Credits", "Group", ""]}
                rows={data.courses.map((row) => [
                  row.code,
                  row.title,
                  String(row.credits),
                  row.result_group,
                  <RowActions
                    key={row.id}
                    onEdit={() => {
                      setCourseId(row.id);
                      setCourse({
                        code: row.code,
                        title: row.title,
                        credits: String(row.credits),
                        department_id: String(row.department_id),
                        result_group: row.result_group,
                      });
                    }}
                    onDelete={() => remove(`/api/v1/admin/courses/${row.id}`, "course")}
                  />,
                ])}
              />
            </>
          ) : null}
        </div>
      </section>
    </AppShell>
  );
}

function RowActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <span className="flex gap-2">
      <button type="button" className="text-xs font-semibold text-[#0B2A4A]" onClick={onEdit}>Edit</button>
      <button type="button" className="text-xs font-semibold text-rose-700" onClick={onDelete}>Delete</button>
    </span>
  );
}

function RecordTable({ headers, rows }: { headers: string[]; rows: (string | JSX.Element)[][] }) {
  return (
    <div className="overflow-x-auto border rounded">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs text-slate-500">
          <tr>
            {headers.map((header) => (
              <th key={header || "actions"} className="px-3 py-2">{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-3 py-2 align-top">{cell}</td>
              ))}
            </tr>
          ))}
          {!rows.length ? (
            <tr>
              <td colSpan={headers.length} className="px-3 py-4 text-slate-500">Nothing saved yet.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminRecordsPage() {
  return (
    <Suspense fallback={<AppShell><p className="p-4 text-sm text-slate-500">Loading records…</p></AppShell>}>
      <RecordsPage />
    </Suspense>
  );
}
