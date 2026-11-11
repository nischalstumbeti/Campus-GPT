"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiDownload, apiFetch, apiUpload } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type StudentRow = {
  student_id: string;
  user_id?: number;
  name: string;
  email: string;
  year: number;
  semester: number;
  section: string;
  batch: string;
  cgpa: number;
  attendance: number;
  credits_completed: number;
  credits_required: number;
  backlogs: number;
  program?: string | null;
  department_code?: string | null;
  residence?: "hostel" | "day_scholar";
  fee_status?: string;
  fee_paid?: number;
  fee_total?: number;
  is_active?: boolean;
};

type Detail = {
  student_id: string;
  name: string;
  email: string;
  year: number;
  semester: number;
  section: string;
  batch: string;
  cgpa: number;
  overall_attendance: number;
  credits_completed: number;
  credits_required: number;
  backlogs: number;
  is_active: boolean;
  photo_url?: string;
};

type FilterOptions = {
  years: number[];
  semesters: number[];
  sections: string[];
  batches: string[];
  departments: { code: string; name: string }[];
  residence: { value: string; label: string }[];
  fee_status: { value: string; label: string }[];
  fee_category: { value: string; label: string }[];
};

type Filters = {
  q: string;
  year: string;
  semester: string;
  section: string;
  batch: string;
  department: string;
  residence: string;
  fee_status: string;
  fee_category: string;
  has_backlogs: string;
  min_attendance: string;
  max_attendance: string;
  is_active: string;
};

const EMPTY_FILTERS: Filters = {
  q: "",
  year: "",
  semester: "",
  section: "",
  batch: "",
  department: "",
  residence: "",
  fee_status: "",
  fee_category: "",
  has_backlogs: "",
  min_attendance: "",
  max_attendance: "",
  is_active: "",
};

function feeBadge(status?: string) {
  const s = (status || "none").toLowerCase();
  const styles: Record<string, string> = {
    paid: "bg-emerald-50 text-emerald-800 border-emerald-200",
    partial: "bg-amber-50 text-amber-800 border-amber-200",
    due: "bg-sky-50 text-sky-800 border-sky-200",
    overdue: "bg-red-50 text-red-800 border-red-200",
    none: "bg-slate-50 text-slate-600 border-slate-200",
  };
  return styles[s] || styles.none;
}

function residenceLabel(r?: string) {
  if (r === "hostel") return "Hostel";
  if (r === "day_scholar") return "Day scholar";
  return "—";
}

export default function AdminStudents() {
  const [items, setItems] = useState<StudentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [editing, setEditing] = useState<Detail | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [gradeForm, setGradeForm] = useState({ student_id: "", course_code: "", grade: "A", section: "" });

  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([k, v]) => k !== "q" && String(v).trim() !== "").length + (filters.q.trim() ? 1 : 0),
    [filters]
  );

  const buildQuery = useCallback((f: Filters) => {
    const params = new URLSearchParams({ limit: "200" });
    if (f.q.trim()) params.set("q", f.q.trim());
    if (f.year) params.set("year", f.year);
    if (f.semester) params.set("semester", f.semester);
    if (f.section) params.set("section", f.section);
    if (f.batch) params.set("batch", f.batch);
    if (f.department) params.set("department", f.department);
    if (f.residence) params.set("residence", f.residence);
    if (f.fee_status) params.set("fee_status", f.fee_status);
    if (f.fee_category) params.set("fee_category", f.fee_category);
    if (f.has_backlogs === "yes") params.set("has_backlogs", "true");
    if (f.has_backlogs === "no") params.set("has_backlogs", "false");
    if (f.min_attendance) params.set("min_attendance", f.min_attendance);
    if (f.max_attendance) params.set("max_attendance", f.max_attendance);
    if (f.is_active === "yes") params.set("is_active", "true");
    if (f.is_active === "no") params.set("is_active", "false");
    return params.toString();
  }, []);

  const load = useCallback(
    async (f = filters) => {
      setBusy(true);
      setMsg("");
      try {
        const d = await apiFetch<{ items: StudentRow[]; total: number }>(`/api/v1/admin/students?${buildQuery(f)}`);
        setItems(d.items || []);
        setTotal(d.total ?? d.items?.length ?? 0);
      } catch (err) {
        setMsg(err instanceof Error ? err.message : "Failed to load students");
      } finally {
        setBusy(false);
      }
    },
    [buildQuery, filters]
  );

  useEffect(() => {
    apiFetch<FilterOptions>("/api/v1/admin/students/filter-options")
      .then(setOptions)
      .catch(() => setOptions(null));
    load(EMPTY_FILTERS).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setFilter = (key: keyof Filters, value: string) => setFilters((prev) => ({ ...prev, [key]: value }));

  const applyQuick = (patch: Partial<Filters>) => {
    const next = { ...EMPTY_FILTERS, ...patch };
    setFilters(next);
    load(next);
  };

  const openEdit = async (studentId: string) => {
    setMsg("");
    const d = await apiFetch<Detail>(`/api/v1/admin/students/${studentId}`);
    setEditing(d);
  };

  const uploadPhoto = async (file: File | null) => {
    if (!file || !editing) return;
    setMsg("");
    try {
      const res = await apiUpload<{ photo_url: string }>(`/api/v1/admin/students/${editing.student_id}/photo`, file);
      setEditing({ ...editing, photo_url: res.photo_url });
      setMsg("Photo updated.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not upload photo");
    }
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/v1/admin/students/${editing.student_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editing.name,
          email: editing.email,
          year: editing.year,
          semester: editing.semester,
          section: editing.section,
          batch: editing.batch,
          cgpa: editing.cgpa,
          overall_attendance: editing.overall_attendance,
          credits_completed: editing.credits_completed,
          credits_required: editing.credits_required,
          backlogs: editing.backlogs,
          is_active: editing.is_active,
        }),
      });
      setMsg(`Saved ${editing.student_id}`);
      setEditing(null);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const mapGrade = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const res = await apiFetch<{ student_id: string; course_code: string; grade: string; action: string }>(
        "/api/v1/admin/students/course-grade",
        {
          method: "POST",
          body: JSON.stringify({
            student_id: gradeForm.student_id.trim(),
            course_code: gradeForm.course_code.trim(),
            grade: gradeForm.grade,
            section: gradeForm.section.trim() || null,
          }),
        }
      );
      setMsg(`${res.action === "updated" ? "Updated" : "Added"} ${res.course_code} for ${res.student_id} with grade ${res.grade}.`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not map the course");
    } finally {
      setBusy(false);
    }
  };

  const importGrades = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await apiUpload<{ message: string; errors: { row: number; error: string }[] }>(
        "/api/v1/admin/students/course-grade/import",
        file
      );
      const extra = res.errors?.length ? ` First issue: row ${res.errors[0].row} — ${res.errors[0].error}` : "";
      setMsg(`${res.message}${extra}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "CSV import failed");
    } finally {
      setBusy(false);
    }
  };

  const summary = useMemo(() => {
    const paid = items.filter((i) => i.fee_status === "paid").length;
    const day = items.filter((i) => i.residence === "day_scholar").length;
    const hostel = items.filter((i) => i.residence === "hostel").length;
    const overdue = items.filter((i) => i.fee_status === "overdue").length;
    return { paid, day, hostel, overdue };
  }, [items]);

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#0B2A4A]">Students</h1>
          <p className="text-sm text-slate-500">
            Filter by fee payment, day scholar / hostel, department, year, and more
          </p>
        </div>
        <p className="text-sm text-slate-500">
          Showing <span className="font-semibold text-[#0B2A4A]">{items.length}</span>
          {total !== items.length ? ` of ${total}` : ""} student{items.length === 1 ? "" : "s"}
          {activeFilterCount ? ` · ${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"}` : ""}
        </p>
      </div>

      {msg && (
        <p className="text-sm mb-3 text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">{msg}</p>
      )}

      <section className="bg-white border rounded-xl p-4 mb-4 shadow-sm space-y-3">
        <div>
          <h2 className="font-semibold text-[#0B2A4A]">Add a course and grade</h2>
          <p className="text-xs text-slate-500">
            Maps one student to a course and letter grade. Grades: O, A+, A, B+, B, C, P, F, RA, AB. Leave section blank to use the student&apos;s section.
          </p>
        </div>
        <form onSubmit={mapGrade} className="flex flex-wrap gap-2 items-end">
          <label className="text-xs text-slate-600">
            Register number
            <input
              required
              value={gradeForm.student_id}
              onChange={(e) => setGradeForm((f) => ({ ...f, student_id: e.target.value }))}
              className="mt-1 block rounded-lg border px-3 py-2 text-sm"
              placeholder="9923004001"
            />
          </label>
          <label className="text-xs text-slate-600">
            Course code
            <input
              required
              value={gradeForm.course_code}
              onChange={(e) => setGradeForm((f) => ({ ...f, course_code: e.target.value }))}
              className="mt-1 block rounded-lg border px-3 py-2 text-sm"
              placeholder="CSE501"
            />
          </label>
          <label className="text-xs text-slate-600">
            Grade
            <select
              value={gradeForm.grade}
              onChange={(e) => setGradeForm((f) => ({ ...f, grade: e.target.value }))}
              className="mt-1 block rounded-lg border px-3 py-2 text-sm"
            >
              {["O", "A+", "A", "B+", "B", "C", "P", "F", "RA", "AB"].map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Section
            <input
              value={gradeForm.section}
              onChange={(e) => setGradeForm((f) => ({ ...f, section: e.target.value }))}
              className="mt-1 block w-20 rounded-lg border px-3 py-2 text-sm"
              placeholder="A"
            />
          </label>
          <button type="submit" disabled={busy} className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm">
            Map grade
          </button>
        </form>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <button
            type="button"
            className="px-3 py-2 rounded-lg border text-sm"
            onClick={() => apiDownload("/api/v1/admin/students/course-grade/template", "course_grade_import.csv").catch((err) => setMsg(err instanceof Error ? err.message : "Download failed"))}
          >
            Download CSV template
          </button>
          <label className="text-sm text-slate-600">
            Import CSV
            <input
              type="file"
              accept=".csv,text/csv"
              disabled={busy}
              className="ml-2 text-sm"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                void importGrades(file);
              }}
            />
          </label>
        </div>
      </section>

      <section className="bg-white border rounded-xl p-4 mb-4 shadow-sm space-y-3">
        <div className="flex flex-wrap gap-2">
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-slate-50" onClick={() => applyQuick({ ...EMPTY_FILTERS })}>
            All
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border border-emerald-200 bg-emerald-50 text-emerald-800" onClick={() => applyQuick({ fee_status: "paid" })}>
            Paid fees
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border border-red-200 bg-red-50 text-red-800" onClick={() => applyQuick({ fee_status: "overdue" })}>
            Overdue
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-200 bg-amber-50 text-amber-800" onClick={() => applyQuick({ fee_status: "due" })}>
            Fee due
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border border-sky-200 bg-sky-50 text-sky-800" onClick={() => applyQuick({ residence: "day_scholar" })}>
            Day scholars
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border border-indigo-200 bg-indigo-50 text-indigo-800" onClick={() => applyQuick({ residence: "hostel" })}>
            Hostel students
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border" onClick={() => applyQuick({ has_backlogs: "yes" })}>
            With backlogs
          </button>
          <button type="button" className="px-3 py-1.5 rounded-lg text-xs font-medium border" onClick={() => applyQuick({ max_attendance: "75" })}>
            Attendance &lt; 75%
          </button>
        </div>

        <form
          className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm"
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <label className="block sm:col-span-2 lg:col-span-2">
            <span className="text-xs text-slate-500">Search</span>
            <input
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              placeholder="ID / name / email"
              value={filters.q}
              onChange={(e) => setFilter("q", e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Residence</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.residence} onChange={(e) => setFilter("residence", e.target.value)}>
              <option value="">All</option>
              {(options?.residence || []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Fee status</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.fee_status} onChange={(e) => setFilter("fee_status", e.target.value)}>
              <option value="">All</option>
              {(options?.fee_status || []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Fee category</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.fee_category} onChange={(e) => setFilter("fee_category", e.target.value)}>
              <option value="">All categories</option>
              {(options?.fee_category || []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Department</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.department} onChange={(e) => setFilter("department", e.target.value)}>
              <option value="">All</option>
              {(options?.departments || []).map((d) => (
                <option key={d.code} value={d.code}>
                  {d.code} — {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Year</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.year} onChange={(e) => setFilter("year", e.target.value)}>
              <option value="">All</option>
              {(options?.years || []).map((y) => (
                <option key={y} value={y}>
                  Year {y}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Semester</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.semester} onChange={(e) => setFilter("semester", e.target.value)}>
              <option value="">All</option>
              {(options?.semesters || []).map((s) => (
                <option key={s} value={s}>
                  Sem {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Section</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.section} onChange={(e) => setFilter("section", e.target.value)}>
              <option value="">All</option>
              {(options?.sections || []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Batch</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.batch} onChange={(e) => setFilter("batch", e.target.value)}>
              <option value="">All</option>
              {(options?.batches || []).map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Backlogs</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.has_backlogs} onChange={(e) => setFilter("has_backlogs", e.target.value)}>
              <option value="">All</option>
              <option value="yes">Has backlogs</option>
              <option value="no">No backlogs</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Account</span>
            <select className="w-full border rounded-lg px-2 py-1.5 mt-0.5" value={filters.is_active} onChange={(e) => setFilter("is_active", e.target.value)}>
              <option value="">All</option>
              <option value="yes">Active</option>
              <option value="no">Inactive</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Min attendance %</span>
            <input
              type="number"
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={filters.min_attendance}
              onChange={(e) => setFilter("min_attendance", e.target.value)}
              min={0}
              max={100}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Max attendance %</span>
            <input
              type="number"
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={filters.max_attendance}
              onChange={(e) => setFilter("max_attendance", e.target.value)}
              min={0}
              max={100}
            />
          </label>
          <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap gap-2 pt-1">
            <button type="submit" disabled={busy} className="px-4 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm disabled:opacity-50">
              Apply filters
            </button>
            <button
              type="button"
              className="px-4 py-2 rounded-lg border text-sm"
              onClick={() => {
                setFilters(EMPTY_FILTERS);
                load(EMPTY_FILTERS);
              }}
            >
              Clear all
            </button>
          </div>
        </form>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1">
          <div className="rounded-lg border px-3 py-2 bg-slate-50">
            <p className="text-slate-500">In view · Hostel</p>
            <p className="text-lg font-semibold text-[#0B2A4A]">{summary.hostel}</p>
          </div>
          <div className="rounded-lg border px-3 py-2 bg-slate-50">
            <p className="text-slate-500">In view · Day scholar</p>
            <p className="text-lg font-semibold text-[#0B2A4A]">{summary.day}</p>
          </div>
          <div className="rounded-lg border px-3 py-2 bg-slate-50">
            <p className="text-slate-500">In view · Paid</p>
            <p className="text-lg font-semibold text-emerald-700">{summary.paid}</p>
          </div>
          <div className="rounded-lg border px-3 py-2 bg-slate-50">
            <p className="text-slate-500">In view · Overdue</p>
            <p className="text-lg font-semibold text-red-700">{summary.overdue}</p>
          </div>
        </div>
      </section>

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 bg-white border rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Residence</th>
                  <th className="px-3 py-2">Fees</th>
                  <th className="px-3 py-2">Year/Sem</th>
                  <th className="px-3 py-2">Att%</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-8 text-center text-slate-400">
                      {busy ? "Loading…" : "No students match these filters."}
                    </td>
                  </tr>
                )}
                {items.map((s) => (
                  <tr key={s.student_id} className="border-t">
                    <td className="px-3 py-2 font-medium whitespace-nowrap">{s.student_id}</td>
                    <td className="px-3 py-2">
                      <p>{s.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {s.department_code || "—"} · {s.batch || "—"} · Sec {s.section || "—"}
                      </p>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">{residenceLabel(s.residence)}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-block text-[11px] font-medium px-2 py-0.5 rounded border capitalize ${feeBadge(s.fee_status)}`}>
                        {(s.fee_status || "none").replace("_", " ")}
                      </span>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        ₹{s.fee_paid ?? 0} / ₹{s.fee_total ?? 0}
                      </p>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      Y{s.year} / S{s.semester}
                    </td>
                    <td className="px-3 py-2">{s.attendance}%</td>
                    <td className="px-3 py-2 whitespace-nowrap space-x-3">
                      <button type="button" className="text-[#0B2A4A] text-xs font-semibold" onClick={() => openEdit(s.student_id)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="text-rose-700 text-xs font-semibold"
                        onClick={() => {
                          if (!s.user_id) return;
                          const phrase = s.student_id;
                          confirmPhrase({
                            title: `Delete ${phrase}`,
                            detail: "Academic, fee, hostel, and message rows for this student are removed from the database.",
                            phrase,
                          }).then((ok) => {
                            if (!ok) return;
                            apiFetch(`/api/v1/admin/users/${s.user_id}`, {
                              method: "DELETE",
                              body: JSON.stringify({ confirm: phrase }),
                            })
                              .then(() => {
                                if (editing?.student_id === s.student_id) setEditing(null);
                                setMsg(`Deleted ${phrase} from the database.`);
                                return load();
                              })
                              .catch((e) => setMsg(e instanceof Error ? e.message : "Delete failed"));
                          });
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-2 bg-white border rounded-xl p-4 shadow-sm h-fit">
          <h2 className="text-sm font-semibold text-[#0B2A4A] mb-3">Edit student</h2>
          {!editing && <p className="text-sm text-slate-400">Select a student to edit details.</p>}
          {editing && (
            <form onSubmit={save} className="space-y-2 text-sm">
              <p className="text-xs text-slate-500 mb-2">{editing.student_id}</p>
              <div className="flex items-center gap-3">
                {editing.photo_url ? (
                  <img src={editing.photo_url} alt="" className="h-20 w-16 object-cover border" />
                ) : (
                  <div className="h-20 w-16 border bg-slate-100" />
                )}
                <div className="space-y-1">
                  <label className="block text-xs text-brand underline cursor-pointer">
                    Upload photo
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      onChange={(e) => uploadPhoto(e.target.files?.[0] || null)}
                    />
                  </label>
                </div>
              </div>
              {(
                [
                  ["name", "Full name", "text"],
                  ["email", "Email", "email"],
                  ["batch", "Batch", "text"],
                  ["section", "Section", "text"],
                ] as const
              ).map(([key, label, type]) => (
                <label key={key} className="block">
                  <span className="text-xs text-slate-500">{label}</span>
                  <input
                    type={type}
                    className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                    value={(editing as any)[key]}
                    onChange={(e) => setEditing({ ...editing, [key]: e.target.value })}
                  />
                </label>
              ))}
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    ["year", "Year"],
                    ["semester", "Semester"],
                    ["cgpa", "CGPA"],
                    ["overall_attendance", "Attendance %"],
                    ["credits_completed", "Credits done"],
                    ["credits_required", "Credits req"],
                    ["backlogs", "Backlogs"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="block">
                    <span className="text-xs text-slate-500">{label}</span>
                    <input
                      type="number"
                      step="any"
                      className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                      value={(editing as any)[key]}
                      onChange={(e) =>
                        setEditing({
                          ...editing,
                          [key]: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                ))}
              </div>
              <label className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  checked={editing.is_active}
                  onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })}
                />
                <span className="text-xs">Active account</span>
              </label>
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={busy} className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm disabled:opacity-50">
                  Save changes
                </button>
                <button type="button" className="px-3 py-2 rounded-lg border text-sm" onClick={() => setEditing(null)}>
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </AppShell>
  );
}
