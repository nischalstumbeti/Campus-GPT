"use client";

import { Fragment, useMemo, useState } from "react";

export type AttendanceSession = {
  id?: number;
  entry_date: string;
  slot_name: string;
  status: string;
};

export type AttendanceCourse = {
  code: string;
  name: string;
  status: "ok" | "attention";
  conducted: number;
  attended: number;
  onduty: number;
  medical: number;
  restricted: number;
  extra: number;
  percentage: number;
  sessions: AttendanceSession[];
};

const STATUS_OPTIONS = [
  { value: "P", label: "P · Present" },
  { value: "A", label: "A · Absent" },
  { value: "OD", label: "OD · On duty" },
  { value: "ML", label: "ML · Medical leave" },
  { value: "RH", label: "RH · Restricted holiday" },
  { value: "EH", label: "EH · Extra hours" },
];

function showDate(iso: string) {
  const [year, month, day] = iso.split("-");
  if (!day) return iso;
  return `${day}/${month}/${year}`;
}

export default function AttendanceBoard({
  courses,
  editable = false,
  onSave,
}: {
  courses: AttendanceCourse[];
  editable?: boolean;
  onSave?: (
    courseCode: string,
    row: { id?: number; entry_date: string; slot_name: string; status: string }
  ) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [sessionQuery, setSessionQuery] = useState("");
  const [sessionPage, setSessionPage] = useState(1);
  const [draft, setDraft] = useState<Record<string, { entry_date: string; slot_name: string; status: string }>>({});
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return courses;
    return courses.filter((course) => `${course.code} ${course.name}`.toLowerCase().includes(q));
  }, [courses, query]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages);
  const start = (safePage - 1) * pageSize;
  const visible = filtered.slice(start, start + pageSize);

  const save = async (course: AttendanceCourse, key: string, row: { id?: number; entry_date: string; slot_name: string; status: string }) => {
    if (!onSave) return;
    if (!row.entry_date || row.slot_name.trim().length < 3) {
      setMsg("Enter the date and slot.");
      return;
    }
    setBusy(key);
    setMsg("");
    try {
      await onSave(course.code, row);
      if (!row.id) {
        setDraft((current) => ({ ...current, [key]: { entry_date: "", slot_name: "", status: "P" } }));
      }
      setMsg("Attendance saved.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not save attendance");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="overflow-x-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm text-slate-600">
        <label className="flex items-center gap-2">
          Show
          <select
            className="border rounded px-2 py-1"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
          >
            {[10, 25, 50].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          entries
        </label>
        <label className="flex items-center gap-2">
          Search
          <input
            className="border rounded px-2 py-1"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>
      {msg ? <p className="px-4 pb-2 text-sm text-brand">{msg}</p> : null}
      <table className="w-full text-sm min-w-[920px]">
        <thead className="uis-table-head text-left text-xs">
          <tr>
            <th className="px-3 py-2" rowSpan={2}>
              Id
            </th>
            <th className="px-3 py-2 text-center" colSpan={2}>
              Course
            </th>
            <th className="px-3 py-2 text-center" colSpan={2}>
              No of Periods
            </th>
            <th className="px-3 py-2 text-center" colSpan={4}>
              Leave Availed
            </th>
            <th className="px-3 py-2" rowSpan={2}>
              Attendance Percentage
            </th>
          </tr>
          <tr>
            <th className="px-3 py-2">code</th>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Conducted</th>
            <th className="px-3 py-2">Attended</th>
            <th className="px-3 py-2">Onduty</th>
            <th className="px-3 py-2">Medical Leave</th>
            <th className="px-3 py-2">Restricted Holiday</th>
            <th className="px-3 py-2">Extra Hours</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((course) => {
            const opened = open === course.code;
            const sessions = course.sessions.filter((row) => {
              const q = sessionQuery.trim().toLowerCase();
              if (!opened || !q) return true;
              return `${row.entry_date} ${row.slot_name} ${row.status}`.toLowerCase().includes(q);
            });
            const sessionPages = Math.max(1, Math.ceil(sessions.length / 10));
            const sessionSafe = Math.min(sessionPage, sessionPages);
            const sessionStart = (sessionSafe - 1) * 10;
            const sessionVisible = sessions.slice(sessionStart, sessionStart + 10);
            const fresh = draft[`${course.code}:new`] || { entry_date: "", slot_name: "", status: "P" };
            return (
              <Fragment key={course.code}>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block h-3 w-3 rounded-full ${course.status === "ok" ? "bg-emerald-500" : "bg-rose-500"}`}
                      aria-label={course.status === "ok" ? "Attendance at or above 75%" : "Attendance below 75%"}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="text-brand font-medium hover:underline"
                      onClick={() => {
                        setOpen(opened ? null : course.code);
                        setSessionPage(1);
                        setSessionQuery("");
                      }}
                    >
                      {course.code}
                    </button>
                  </td>
                  <td className="px-3 py-2">{course.name}</td>
                  <td className="px-3 py-2">{course.conducted}</td>
                  <td className="px-3 py-2">{course.attended}</td>
                  <td className="px-3 py-2">{course.onduty}</td>
                  <td className="px-3 py-2">{course.medical}</td>
                  <td className="px-3 py-2">{course.restricted}</td>
                  <td className="px-3 py-2">{course.extra}</td>
                  <td className="px-3 py-2">{course.percentage.toFixed(1)}</td>
                </tr>
                {opened ? (
                  <tr className="bg-slate-100">
                    <td colSpan={10} className="px-3 py-3">
                      <p className="inline-block mb-2 rounded bg-sky-500 px-2 py-0.5 text-xs font-semibold text-white">
                        #{course.code} · Full view
                      </p>
                      <div className="bg-white border border-slate-200">
                        <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-2 text-sm text-slate-600">
                          <span>Show 10 entries</span>
                          <label className="flex items-center gap-2">
                            Search
                            <input
                              className="border rounded px-2 py-1"
                              value={sessionQuery}
                              onChange={(e) => {
                                setSessionQuery(e.target.value);
                                setSessionPage(1);
                              }}
                            />
                          </label>
                        </div>
                        <table className="w-full text-sm">
                          <thead className="text-left text-xs text-slate-500">
                            <tr>
                              <th className="px-3 py-2">Entry Date</th>
                              <th className="px-3 py-2">Slot Name</th>
                              <th className="px-3 py-2">Status</th>
                              {editable ? <th className="px-3 py-2" /> : null}
                            </tr>
                          </thead>
                          <tbody>
                            {sessionVisible.map((row) => {
                              const key = `${course.code}:${row.id}`;
                              const edit = draft[key] || {
                                entry_date: row.entry_date,
                                slot_name: row.slot_name,
                                status: row.status,
                              };
                              return (
                                <tr key={key} className="border-t">
                                  <td className="px-3 py-2">
                                    {editable ? (
                                      <input
                                        type="date"
                                        className="border rounded px-2 py-1"
                                        value={edit.entry_date}
                                        onChange={(e) =>
                                          setDraft((current) => ({ ...current, [key]: { ...edit, entry_date: e.target.value } }))
                                        }
                                      />
                                    ) : (
                                      showDate(row.entry_date)
                                    )}
                                  </td>
                                  <td className="px-3 py-2">
                                    {editable ? (
                                      <input
                                        className="border rounded px-2 py-1 w-full"
                                        value={edit.slot_name}
                                        onChange={(e) =>
                                          setDraft((current) => ({ ...current, [key]: { ...edit, slot_name: e.target.value } }))
                                        }
                                      />
                                    ) : (
                                      row.slot_name
                                    )}
                                  </td>
                                  <td className="px-3 py-2">
                                    {editable ? (
                                      <select
                                        className="border rounded px-2 py-1"
                                        value={edit.status}
                                        onChange={(e) =>
                                          setDraft((current) => ({ ...current, [key]: { ...edit, status: e.target.value } }))
                                        }
                                      >
                                        {STATUS_OPTIONS.map((option) => (
                                          <option key={option.value} value={option.value}>
                                            {option.label}
                                          </option>
                                        ))}
                                      </select>
                                    ) : (
                                      row.status
                                    )}
                                  </td>
                                  {editable ? (
                                    <td className="px-3 py-2">
                                      <button
                                        type="button"
                                        className="px-3 py-1 rounded bg-brand text-white text-xs disabled:opacity-50"
                                        disabled={busy === key}
                                        onClick={() => save(course, key, { id: row.id, ...edit })}
                                      >
                                        Save
                                      </button>
                                    </td>
                                  ) : null}
                                </tr>
                              );
                            })}
                            {editable ? (
                              <tr className="border-t bg-slate-50">
                                <td className="px-3 py-2">
                                  <input
                                    type="date"
                                    className="border rounded px-2 py-1"
                                    value={fresh.entry_date}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: { ...fresh, entry_date: e.target.value },
                                      }))
                                    }
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    className="border rounded px-2 py-1 w-full"
                                    placeholder="08.00 AM - 08.50 AM"
                                    value={fresh.slot_name}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: { ...fresh, slot_name: e.target.value },
                                      }))
                                    }
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <select
                                    className="border rounded px-2 py-1"
                                    value={fresh.status}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: { ...fresh, status: e.target.value },
                                      }))
                                    }
                                  >
                                    {STATUS_OPTIONS.map((option) => (
                                      <option key={option.value} value={option.value}>
                                        {option.label}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                                <td className="px-3 py-2">
                                  <button
                                    type="button"
                                    className="px-3 py-1 rounded bg-brand text-white text-xs disabled:opacity-50"
                                    disabled={busy === `${course.code}:new`}
                                    onClick={() => save(course, `${course.code}:new`, fresh)}
                                  >
                                    Add
                                  </button>
                                </td>
                              </tr>
                            ) : null}
                            {!sessions.length && !editable ? (
                              <tr>
                                <td colSpan={3} className="px-3 py-3 text-slate-500">
                                  No periods entered.
                                </td>
                              </tr>
                            ) : null}
                          </tbody>
                        </table>
                        <div className="flex justify-end gap-1 px-3 py-2 text-sm">
                          <button
                            type="button"
                            className="px-3 py-1 border rounded disabled:opacity-40"
                            disabled={sessionSafe <= 1}
                            onClick={() => setSessionPage(sessionSafe - 1)}
                          >
                            Previous
                          </button>
                          <span className="px-3 py-1 rounded bg-brand text-white">{sessionSafe}</span>
                          <button
                            type="button"
                            className="px-3 py-1 border rounded disabled:opacity-40"
                            disabled={sessionSafe >= sessionPages}
                            onClick={() => setSessionPage(sessionSafe + 1)}
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
          {!visible.length ? (
            <tr>
              <td colSpan={10} className="px-3 py-4 text-slate-500">
                No courses match.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
      <div className="flex items-center justify-between px-4 py-3 text-sm text-slate-500">
        <span>
          Showing {filtered.length ? start + 1 : 0} to {Math.min(start + pageSize, filtered.length)} of {filtered.length} entries
        </span>
        <div className="flex gap-1">
          <button type="button" className="px-3 py-1 border rounded disabled:opacity-40" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>
            Previous
          </button>
          <span className="px-3 py-1 rounded bg-brand text-white">{safePage}</span>
          <button type="button" className="px-3 py-1 border rounded disabled:opacity-40" disabled={safePage >= pages} onClick={() => setPage(safePage + 1)}>
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
