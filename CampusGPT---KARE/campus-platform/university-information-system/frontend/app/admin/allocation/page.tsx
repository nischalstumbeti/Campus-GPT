"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type Faculty = { id: number; faculty_id: string; name: string };
type CourseOption = { id: number; code: string; title: string };
type DepartmentOption = { code: string; name: string };
type Group = { department_code: string; batch: string; section: string; semester: number; students: number };
type Offering = {
  offering_id: number;
  code: string;
  title: string;
  section: string;
  semester: number;
  academic_year: string;
  faculty_profile_id: number | null;
  faculty_name: string;
  students: number;
};
type RosterStudent = {
  sno: number;
  student_id: string;
  name: string;
  section: string;
  percentage: number;
};

export default function AllocationPage() {
  const [faculty, setFaculty] = useState<Faculty[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [courseId, setCourseId] = useState("");
  const [department, setDepartment] = useState("");
  const [batch, setBatch] = useState("");
  const [scope, setScope] = useState<"batch" | "section">("batch");
  const [section, setSection] = useState("");
  const [facultyMode, setFacultyMode] = useState<"same" | "different">("same");
  const [facultyId, setFacultyId] = useState("");
  const [sectionFaculty, setSectionFaculty] = useState<Record<string, string>>({});
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [picks, setPicks] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<Offering | null>(null);
  const [roster, setRoster] = useState<RosterStudent[]>([]);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [advisors, setAdvisors] = useState<{ id: number; scope: string; section: string; batch: string; student_id: string; student_name: string; faculty_name: string }[]>([]);
  const [advisorScope, setAdvisorScope] = useState<"section" | "student">("section");
  const [advisorBatch, setAdvisorBatch] = useState("");
  const [advisorSection, setAdvisorSection] = useState("");
  const [advisorStudent, setAdvisorStudent] = useState("");
  const [advisorFaculty, setAdvisorFaculty] = useState("");

  const load = () =>
    apiFetch<{ faculty: Faculty[]; offerings: Offering[]; courses: CourseOption[]; departments: DepartmentOption[]; groups: Group[] }>(
      "/api/v1/admin/allocations"
    ).then((data) => {
      setFaculty(data.faculty || []);
      setCourses(data.courses || []);
      setDepartments(data.departments || []);
      setGroups(data.groups || []);
      setOfferings(data.offerings || []);
      const next: Record<number, string> = {};
      (data.offerings || []).forEach((row) => {
        next[row.offering_id] = row.faculty_profile_id ? String(row.faculty_profile_id) : "";
      });
      setPicks(next);
    });

  const loadRoster = (row: Offering) => {
    setSelected(row);
    apiFetch<{ students: RosterStudent[] }>(`/api/v1/admin/allocations/${row.offering_id}/students`)
      .then((data) => setRoster(data.students || []))
      .catch((e) => setErr(e.message));
  };

  const loadAdvisors = () =>
    apiFetch<{ items: typeof advisors }>("/api/v1/admin/advisors").then((data) => setAdvisors(data.items || []));

  useEffect(() => {
    load().catch((e) => setErr(e.message));
    loadAdvisors().catch((e) => setErr(e.message));
  }, []);

  const batches = [...new Set(groups.filter((row) => row.department_code === department).map((row) => row.batch))];
  const matching = groups.filter((row) => row.department_code === department && row.batch === batch);
  const sections = [...new Set(matching.map((row) => row.section))];
  const studentCount = matching
    .filter((row) => scope === "batch" || row.section === section)
    .reduce((sum, row) => sum + row.students, 0);

  const allocate = async () => {
    setErr("");
    setMessage("");
    if (!courseId || !department || !batch) {
      setErr("Choose the course, department, and batch.");
      return;
    }
    if (scope === "section" && !section) {
      setErr("Choose the section.");
      return;
    }
    const faculties =
      scope === "batch" && facultyMode === "different"
        ? sections.map((name) => ({ section: name, faculty_profile_id: sectionFaculty[name] ? Number(sectionFaculty[name]) : null }))
        : [];
    const result = await apiFetch<{ added: number; course: string; sections: { section: string; added: number; students: number }[] }>(
      "/api/v1/admin/allocations/apply",
      {
        method: "POST",
        body: JSON.stringify({
          course_id: Number(courseId),
          department_code: department,
          batch,
          scope,
          section: scope === "section" ? section : null,
          faculty_profile_id: facultyMode === "same" || scope === "section" ? (facultyId ? Number(facultyId) : null) : null,
          faculties,
        }),
      }
    );
    const names = result.sections.map((row) => `${row.section} (${row.students})`).join(", ");
    setMessage(
      `${result.course} allocated to ${result.added} new student${result.added === 1 ? "" : "s"} across section ${names}.`
    );
    await load();
  };

  const removeCourse = async () => {
    const course = courses.find((row) => String(row.id) === courseId);
    if (!course) {
      setErr("Choose the course to delete.");
      return;
    }
    if (!(await confirmPhrase({
      title: `Delete ${course.code}`,
      detail: "Sections, enrollments, marks, attendance, timetable periods, and exam venues for this course are removed from the database.",
      phrase: course.code,
    }))) return;
    setErr("");
    const result = await apiFetch<{ deleted: string; acknowledgement?: { number: string; email_sent: boolean } }>(`/api/v1/admin/courses/${course.id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: course.code }),
    });
    setCourseId("");
    setMessage(`Deleted ${result.deleted} from the database.${result.acknowledgement ? ` Slip ${result.acknowledgement.number}.` : ""}`);
    await load();
  };

  const removeOffering = async (row: Offering) => {
    const phrase = `${row.code}-${row.section}`;
    if (!(await confirmPhrase({
      title: `Delete ${row.code} section ${row.section}`,
      detail: "Enrollments, marks, and attendance for this section are removed from the database.",
      phrase,
    }))) return;
    setErr("");
    const result = await apiFetch<{ deleted: string; acknowledgement?: { number: string } }>(`/api/v1/admin/allocations/${row.offering_id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: phrase }),
    });
    if (selected?.offering_id === row.offering_id) {
      setSelected(null);
      setRoster([]);
    }
    setMessage(`Deleted ${result.deleted} from the database.${result.acknowledgement ? ` Slip ${result.acknowledgement.number}.` : ""}`);
    await load();
  };

  const removeAdvisor = async (id: number) => {
    const advisor = advisors.find((row) => row.id === id);
    const phrase = advisor?.faculty_name || "REMOVE";
    if (!(await confirmPhrase({
      title: "Remove faculty advisor",
      detail: "This mapping is removed from the database.",
      phrase,
    }))) return;
    const data = await apiFetch<{ items: typeof advisors }>(`/api/v1/admin/advisors/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: phrase }),
    });
    setAdvisors(data.items || []);
    setMessage("Advisor mapping removed.");
  };

  const advisorBatches = [...new Set(groups.map((row) => row.batch))];
  const advisorSections = [...new Set(groups.filter((row) => !advisorBatch || row.batch === advisorBatch).map((row) => row.section))];

  const saveAdvisor = async () => {
    setErr("");
    setMessage("");
    if (!advisorFaculty) {
      setErr("Choose the faculty advisor.");
      return;
    }
    const data = await apiFetch<{ items: typeof advisors }>("/api/v1/admin/advisors", {
      method: "POST",
      body: JSON.stringify({
        faculty_profile_id: Number(advisorFaculty),
        scope: advisorScope,
        section: advisorSection,
        batch: advisorBatch,
        student_id: advisorStudent,
      }),
    });
    setAdvisors(data.items || []);
    setMessage(advisorScope === "student" ? `Faculty advisor mapped for ${advisorStudent}.` : `Faculty advisor mapped for section ${advisorSection}.`);
  };

  const saveFaculty = async (row: Offering) => {
    setErr("");
    setMessage("");
    const value = picks[row.offering_id];
    await apiFetch(`/api/v1/admin/allocations/${row.offering_id}`, {
      method: "PUT",
      body: JSON.stringify({ faculty_profile_id: value ? Number(value) : null }),
    });
    setMessage(`${row.code} section ${row.section} is assigned.`);
    await load();
  };

  const mapSection = async (row: Offering) => {
    setErr("");
    setMessage("");
    const result = await apiFetch<{ added: number; section: string; semester: number }>(
      `/api/v1/admin/allocations/${row.offering_id}/map-section`,
      { method: "POST" }
    );
    setMessage(
      result.added
        ? `Mapped ${result.added} student${result.added === 1 ? "" : "s"} from section ${result.section}, semester ${result.semester}.`
        : `Section ${result.section}, semester ${result.semester} is already mapped.`
    );
    await load();
    loadRoster({ ...row, students: row.students + result.added });
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Course allocation</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">
          Give a course to every student in a department batch, or only to one section. The same faculty can teach every section, or each section can have a different faculty.
        </p>
        <div className="p-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm border-b border-slate-100">
          <label className="block">
            <span className="text-xs text-slate-500">Course</span>
            <select className="mt-1 w-full border rounded px-2 py-1.5" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
              <option value="">Select course</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.code} · {course.title}
                </option>
              ))}
            </select>
            <button type="button" className="mt-2 text-xs font-semibold text-rose-700" onClick={() => removeCourse().catch((e) => setErr(e.message))}>
              Delete this course and its records
            </button>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Department</span>
            <select
              className="mt-1 w-full border rounded px-2 py-1.5"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setBatch("");
                setSection("");
              }}
            >
              <option value="">Select department</option>
              {departments.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.code} · {row.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Batch</span>
            <select className="mt-1 w-full border rounded px-2 py-1.5" value={batch} onChange={(e) => { setBatch(e.target.value); setSection(""); }}>
              <option value="">Select batch</option>
              {batches.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Who needs this subject</span>
            <select className="mt-1 w-full border rounded px-2 py-1.5" value={scope} onChange={(e) => setScope(e.target.value as "batch" | "section")}>
              <option value="batch">All sections in this batch</option>
              <option value="section">Only one section</option>
            </select>
          </label>
          {scope === "section" ? (
            <label className="block">
              <span className="text-xs text-slate-500">Section</span>
              <select className="mt-1 w-full border rounded px-2 py-1.5" value={section} onChange={(e) => setSection(e.target.value)}>
                <option value="">Select section</option>
                {sections.map((value) => (
                  <option key={value} value={value}>
                    Section {value} · {matching.filter((row) => row.section === value).reduce((sum, row) => sum + row.students, 0)} students
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block">
              <span className="text-xs text-slate-500">Faculty</span>
              <select className="mt-1 w-full border rounded px-2 py-1.5" value={facultyMode} onChange={(e) => setFacultyMode(e.target.value as "same" | "different")}>
                <option value="same">Same faculty for every section</option>
                <option value="different">Different faculty for each section</option>
              </select>
            </label>
          )}
          {scope === "section" || facultyMode === "same" ? (
            <label className="block">
              <span className="text-xs text-slate-500">Faculty</span>
              <select className="mt-1 w-full border rounded px-2 py-1.5" value={facultyId} onChange={(e) => setFacultyId(e.target.value)}>
                <option value="">Unassigned</option>
                {faculty.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name} · {person.faculty_id}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap items-center gap-3">
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white" onClick={() => allocate().catch((e) => setErr(e.message))}>
              Allocate course
            </button>
            <span className="text-xs text-slate-500">{department && batch ? `${studentCount} student${studentCount === 1 ? "" : "s"} match this choice.` : ""}</span>
          </div>
          {scope === "batch" && facultyMode === "different" && sections.length ? (
            <div className="sm:col-span-2 lg:col-span-3 grid sm:grid-cols-2 gap-2">
              {sections.map((name) => (
                <label key={name} className="block">
                  <span className="text-xs text-slate-500">
                    Section {name} · {matching.filter((row) => row.section === name).reduce((sum, row) => sum + row.students, 0)} students
                  </span>
                  <select
                    className="mt-1 w-full border rounded px-2 py-1.5"
                    value={sectionFaculty[name] || ""}
                    onChange={(e) => setSectionFaculty((prev) => ({ ...prev, [name]: e.target.value }))}
                  >
                    <option value="">Unassigned</option>
                    {faculty.map((person) => (
                      <option key={person.id} value={person.id}>
                        {person.name} · {person.faculty_id}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          ) : null}
        </div>
        {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
        {message ? <p className="px-4 py-2 text-sm text-emerald-700">{message}</p> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Course</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Sem</th>
                <th className="px-3 py-2">Students</th>
                <th className="px-3 py-2">Faculty</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {offerings.map((row) => (
                <tr key={row.offering_id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{row.code}</td>
                  <td className="px-3 py-2">{row.title}</td>
                  <td className="px-3 py-2">{row.section}</td>
                  <td className="px-3 py-2">{row.semester}</td>
                  <td className="px-3 py-2">{row.students}</td>
                  <td className="px-3 py-2">
                    <select
                      className="border rounded px-2 py-1 min-w-44"
                      value={picks[row.offering_id] ?? ""}
                      onChange={(e) => setPicks((prev) => ({ ...prev, [row.offering_id]: e.target.value }))}
                    >
                      <option value="">Unassigned</option>
                      {faculty.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.name} · {person.faculty_id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap space-x-2">
                    <button type="button" className="text-[#0B2A4A] font-medium" onClick={() => saveFaculty(row).catch((e) => setErr(e.message))}>
                      Save
                    </button>
                    <button type="button" className="text-emerald-700 font-medium" onClick={() => mapSection(row).catch((e) => setErr(e.message))}>
                      Map students
                    </button>
                    <button type="button" className="text-slate-600 font-medium" onClick={() => loadRoster(row)}>
                      View
                    </button>
                    <button
                      type="button"
                      className="text-rose-700 font-medium"
                      onClick={() => removeOffering(row).catch((e) => setErr(e.message))}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="uis-panel mt-4">
        <h2 className="uis-panel-title">
          {selected ? `${selected.code} · Section ${selected.section}` : "Course students"}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">S.No</th>
                <th className="px-3 py-2">Register number</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Attendance %</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((student) => (
                <tr key={student.student_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{student.sno}</td>
                  <td className="px-3 py-2 font-medium">{student.student_id}</td>
                  <td className="px-3 py-2">{student.name}</td>
                  <td className="px-3 py-2">{student.section}</td>
                  <td className="px-3 py-2">{student.percentage.toFixed(1)}</td>
                </tr>
              ))}
              {!roster.length ? (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-slate-500">
                    Choose View on a course, or map the section students first.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section className="uis-panel mt-4">
        <h2 className="uis-panel-title">Faculty advisor</h2>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-100">
          Map one faculty as the advisor or mentor for a section, or for a single student. That faculty handles the student’s leave and other requests. A student mapping overrides the section mapping.
        </p>
        <div className="p-4 grid sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
          <label className="block">
            <span className="text-xs text-slate-500">Map</span>
            <select className="mt-1 w-full border rounded px-2 py-1.5" value={advisorScope} onChange={(e) => setAdvisorScope(e.target.value as "section" | "student")}>
              <option value="section">A section</option>
              <option value="student">One student</option>
            </select>
          </label>
          {advisorScope === "section" ? (
            <>
              <label className="block">
                <span className="text-xs text-slate-500">Batch</span>
                <select className="mt-1 w-full border rounded px-2 py-1.5" value={advisorBatch} onChange={(e) => setAdvisorBatch(e.target.value)}>
                  <option value="">Select batch</option>
                  {advisorBatches.map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Section</span>
                <select className="mt-1 w-full border rounded px-2 py-1.5" value={advisorSection} onChange={(e) => setAdvisorSection(e.target.value)}>
                  <option value="">Select section</option>
                  {advisorSections.map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <label className="block">
              <span className="text-xs text-slate-500">Register number</span>
              <input className="mt-1 w-full border rounded px-2 py-1.5" value={advisorStudent} onChange={(e) => setAdvisorStudent(e.target.value)} />
            </label>
          )}
          <label className="block">
            <span className="text-xs text-slate-500">Faculty advisor</span>
            <select className="mt-1 w-full border rounded px-2 py-1.5" value={advisorFaculty} onChange={(e) => setAdvisorFaculty(e.target.value)}>
              <option value="">Select faculty</option>
              {faculty.map((person) => (
                <option key={person.id} value={person.id}>{person.name} · {person.faculty_id}</option>
              ))}
            </select>
          </label>
          <div className="sm:col-span-2 lg:col-span-3">
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white" onClick={() => saveAdvisor().catch((e) => setErr(e.message))}>
              Map advisor
            </button>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left">
            <tr>
              <th className="px-3 py-2">Mapped to</th>
              <th className="px-3 py-2">Faculty advisor</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {advisors.map((row) => (
              <tr key={row.id} className="border-t border-slate-100">
                <td className="px-3 py-2">
                  {row.scope === "student" ? `${row.student_id} · ${row.student_name}` : `Section ${row.section}${row.batch ? ` · ${row.batch}` : ""}`}
                </td>
                <td className="px-3 py-2">{row.faculty_name}</td>
                <td className="px-3 py-2">
                  <button type="button" className="text-rose-700 font-medium" onClick={() => removeAdvisor(row.id).catch((e) => setErr(e.message))}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!advisors.length ? (
              <tr><td colSpan={2} className="px-3 py-4 text-slate-500">No faculty advisor is mapped yet.</td></tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
