"use client";

import { Fragment, useMemo, useState } from "react";

export type MarkAssessment = {
  id?: number;
  assessment: string;
  score: number | null;
  max_score: number;
};

export type MarkCourse = {
  code: string;
  name: string;
  status: "ok" | "attention";
  assessments: MarkAssessment[];
};

function displayScore(row: MarkAssessment) {
  if (row.score === null || row.score === undefined) return "—";
  return Number.isInteger(row.score) ? String(row.score) : String(row.score);
}

export default function MarksBoard({
  courses,
  editable = false,
  onSave,
}: {
  courses: MarkCourse[];
  editable?: boolean;
  onSave?: (courseCode: string, row: { assessment: string; score: number; max_score: number }) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, { assessment: string; score: string; max: string }>>({});
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

  const saveRow = async (course: MarkCourse, row: MarkAssessment) => {
    if (!onSave) return;
    const key = `${course.code}:${row.id || row.assessment}`;
    const edit = draft[key];
    const score = Number(edit?.score ?? row.score);
    const max = Number(edit?.max ?? row.max_score);
    const assessment = (edit?.assessment || row.assessment).trim();
    if (!assessment || Number.isNaN(score) || Number.isNaN(max)) {
      setMsg("Enter an assessment and a numeric mark.");
      return;
    }
    setBusy(key);
    setMsg("");
    try {
      await onSave(course.code, { assessment, score, max_score: max });
      setMsg("Marks saved.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not save marks");
    } finally {
      setBusy("");
    }
  };

  const addRow = async (course: MarkCourse) => {
    const key = `${course.code}:new`;
    const edit = draft[key] || { assessment: "", score: "", max: "50" };
    if (!onSave) return;
    setBusy(key);
    setMsg("");
    try {
      await onSave(course.code, {
        assessment: edit.assessment.trim(),
        score: Number(edit.score),
        max_score: Number(edit.max || 50),
      });
      setDraft((current) => ({ ...current, [key]: { assessment: "", score: "", max: "50" } }));
      setMsg("Marks saved.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not save marks");
    } finally {
      setBusy("");
    }
  };

  return (
    <div>
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
      <table className="w-full text-sm">
        <thead className="uis-table-head text-left text-xs">
          <tr>
            <th className="px-3 py-2 w-16">Id</th>
            <th className="px-3 py-2">Course Code</th>
            <th className="px-3 py-2">Name</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((course) => {
            const opened = open === course.code;
            return (
              <Fragment key={course.code}>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block h-3 w-3 rounded-full ${course.status === "ok" ? "bg-emerald-500" : "bg-rose-500"}`}
                      aria-label={course.status === "ok" ? "Marks recorded" : "Marks missing"}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button type="button" className="text-brand font-medium hover:underline" onClick={() => setOpen(opened ? null : course.code)}>
                      {course.code}
                    </button>
                  </td>
                  <td className="px-3 py-2">{course.name}</td>
                </tr>
                {opened ? (
                  <tr key={`${course.code}-detail`} className="bg-slate-100">
                    <td colSpan={3} className="px-3 py-3">
                      <p className="inline-block mb-2 rounded bg-sky-500 px-2 py-0.5 text-xs font-semibold text-white">
                        #{course.code} · Full view
                      </p>
                      <div className="bg-white border border-slate-200">
                        <table className="w-full text-sm">
                          <thead className="text-left text-xs text-slate-500">
                            <tr>
                              <th className="px-3 py-2">Sno</th>
                              <th className="px-3 py-2">Assessment</th>
                              <th className="px-3 py-2">Marks</th>
                              {editable ? <th className="px-3 py-2">Maximum</th> : null}
                              {editable ? <th className="px-3 py-2" /> : null}
                            </tr>
                          </thead>
                          <tbody>
                            {course.assessments.map((row, index) => {
                              const key = `${course.code}:${row.id || row.assessment}`;
                              const edit = draft[key];
                              return (
                                <tr key={key} className="border-t">
                                  <td className="px-3 py-2">{index + 1}</td>
                                  <td className="px-3 py-2">
                                    {editable ? (
                                      <input
                                        className="border rounded px-2 py-1 w-full"
                                        value={edit?.assessment ?? row.assessment}
                                        onChange={(e) =>
                                          setDraft((current) => ({
                                            ...current,
                                            [key]: {
                                              assessment: e.target.value,
                                              score: current[key]?.score ?? String(row.score ?? ""),
                                              max: current[key]?.max ?? String(row.max_score),
                                            },
                                          }))
                                        }
                                      />
                                    ) : (
                                      row.assessment
                                    )}
                                  </td>
                                  <td className="px-3 py-2">
                                    {editable ? (
                                      <input
                                        className="border rounded px-2 py-1 w-24"
                                        value={edit?.score ?? displayScore(row)}
                                        onChange={(e) =>
                                          setDraft((current) => ({
                                            ...current,
                                            [key]: {
                                              assessment: current[key]?.assessment ?? row.assessment,
                                              score: e.target.value,
                                              max: current[key]?.max ?? String(row.max_score),
                                            },
                                          }))
                                        }
                                      />
                                    ) : (
                                      displayScore(row)
                                    )}
                                  </td>
                                  {editable ? (
                                    <td className="px-3 py-2">
                                      <input
                                        className="border rounded px-2 py-1 w-24"
                                        value={edit?.max ?? String(row.max_score)}
                                        onChange={(e) =>
                                          setDraft((current) => ({
                                            ...current,
                                            [key]: {
                                              assessment: current[key]?.assessment ?? row.assessment,
                                              score: current[key]?.score ?? String(row.score ?? ""),
                                              max: e.target.value,
                                            },
                                          }))
                                        }
                                      />
                                    </td>
                                  ) : null}
                                  {editable ? (
                                    <td className="px-3 py-2">
                                      <button
                                        type="button"
                                        className="px-3 py-1 rounded bg-brand text-white text-xs disabled:opacity-50"
                                        disabled={busy === key}
                                        onClick={() => saveRow(course, row)}
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
                                <td className="px-3 py-2">{course.assessments.length + 1}</td>
                                <td className="px-3 py-2">
                                  <input
                                    className="border rounded px-2 py-1 w-full"
                                    placeholder="Sessional-I"
                                    value={draft[`${course.code}:new`]?.assessment || ""}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: {
                                          assessment: e.target.value,
                                          score: current[`${course.code}:new`]?.score || "",
                                          max: current[`${course.code}:new`]?.max || "50",
                                        },
                                      }))
                                    }
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    className="border rounded px-2 py-1 w-24"
                                    placeholder="40"
                                    value={draft[`${course.code}:new`]?.score || ""}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: {
                                          assessment: current[`${course.code}:new`]?.assessment || "",
                                          score: e.target.value,
                                          max: current[`${course.code}:new`]?.max || "50",
                                        },
                                      }))
                                    }
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    className="border rounded px-2 py-1 w-24"
                                    value={draft[`${course.code}:new`]?.max || "50"}
                                    onChange={(e) =>
                                      setDraft((current) => ({
                                        ...current,
                                        [`${course.code}:new`]: {
                                          assessment: current[`${course.code}:new`]?.assessment || "",
                                          score: current[`${course.code}:new`]?.score || "",
                                          max: e.target.value,
                                        },
                                      }))
                                    }
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <button
                                    type="button"
                                    className="px-3 py-1 rounded bg-brand text-white text-xs disabled:opacity-50"
                                    disabled={busy === `${course.code}:new`}
                                    onClick={() => addRow(course)}
                                  >
                                    Add
                                  </button>
                                </td>
                              </tr>
                            ) : null}
                            {!course.assessments.length && !editable ? (
                              <tr>
                                <td colSpan={3} className="px-3 py-3 text-slate-500">
                                  No assessments entered.
                                </td>
                              </tr>
                            ) : null}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
          {!visible.length ? (
            <tr>
              <td colSpan={3} className="px-3 py-4 text-slate-500">
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
