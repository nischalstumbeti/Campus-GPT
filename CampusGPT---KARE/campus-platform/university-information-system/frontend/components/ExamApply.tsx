"use client";

import { useEffect, useState } from "react";
import AckSlip from "@/components/AckSlip";
import { apiFetch } from "@/lib/api";

type CourseRow = {
  course_id: number;
  code: string;
  name: string;
  semester: number;
  letter: string;
  applied: boolean;
  application_id?: number | null;
  status: string;
  advisor_status?: string;
  hod_status?: string;
};

type WindowData = {
  enabled: boolean;
  note: string;
  fee: number;
  courses: CourseRow[];
};

const COPY: Record<string, { closed: string; empty: string; action: string }> = {
  revaluation: {
    closed: "Revaluation is closed. You can apply after an administrator opens it.",
    empty: "No published results are open for revaluation.",
    action: "Apply",
  },
  arrear: {
    closed: "Arrear registration is closed. You can apply after an administrator opens it.",
    empty: "You have no arrear courses for this semester.",
    action: "Register",
  },
  backlog: {
    closed: "Backlog registration is closed. You can apply after an administrator opens it.",
    empty: "You have no backlog courses from earlier semesters.",
    action: "Register",
  },
};

export default function ExamApply({ kind }: { kind: "revaluation" | "arrear" | "backlog" }) {
  const [data, setData] = useState<WindowData | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(0);
  const [slip, setSlip] = useState<any>(null);
  const [pending, setPending] = useState<CourseRow | null>(null);
  const text = COPY[kind];

  const stage = (course: CourseRow) => {
    if (course.status === "approved") return "Approved";
    if (course.status === "rejected") return "Not approved";
    if (course.advisor_status === "approved") return "Waiting for HoD";
    return "Waiting for faculty advisor";
  };

  const load = () => {
    apiFetch<WindowData>(`/api/v1/student/applications/${kind}`)
      .then(setData)
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    setErr("");
    setData(null);
    load();
  }, [kind]);

  const apply = async (course: CourseRow) => {
    setBusy(course.course_id);
    setErr("");
    try {
      const result = await apiFetch<{ acknowledgement?: { number: string; status: string } }>(`/api/v1/student/applications/${kind}`, {
        method: "POST",
        body: JSON.stringify({ course_id: course.course_id }),
      });
      if (result.acknowledgement) {
        setErr(`Slip ${result.acknowledgement.number}. Status: ${result.acknowledgement.status}. Open Acknowledgements to print it.`);
      }
      setPending(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not submit");
    } finally {
      setBusy(0);
    }
  };

  if (!data) {
    return err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : <p className="px-4 py-4 text-sm text-slate-500">Loading…</p>;
  }

  return (
    <div>
      <div className="px-4 py-3 text-sm border-b border-slate-100">
        <p className={data.enabled ? "text-emerald-700" : "text-slate-600"}>
          {data.enabled ? "Applications are open." : text.closed}
        </p>
        {data.note ? <p className="mt-1 text-slate-600">{data.note}</p> : null}
        {data.enabled && data.fee > 0 ? <p className="mt-1 text-slate-500">Fee ₹{data.fee}</p> : null}
      </div>
      {err ? <p className={`px-4 py-2 text-sm ${err.startsWith("Slip ") ? "text-emerald-700" : "text-red-600"}`}>{err}</p> : null}
      {data.enabled ? (
        <table className="w-full text-sm">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-3 py-2">Semester</th>
              <th className="px-3 py-2">Course</th>
              <th className="px-3 py-2">Grade</th>
              <th className="px-3 py-2">Application</th>
            </tr>
          </thead>
          <tbody>
            {data.courses.map((course) => (
              <tr key={course.course_id} className="border-t border-slate-100">
                <td className="px-3 py-2">{course.semester}</td>
                <td className="px-3 py-2">
                  {course.code} · {course.name}
                </td>
                <td className="px-3 py-2">{course.letter}</td>
                <td className="px-3 py-2">
                  {course.applied ? (
                    <span className="text-sm">
                      <span className="text-emerald-700">{stage(course)}</span>
                      {course.status === "approved" && course.application_id ? (
                        <button
                          type="button"
                          className="ml-2 text-brand underline"
                          onClick={() =>
                            apiFetch(`/api/v1/student/slips/exam/${course.application_id}`).then(setSlip).catch((e) => setErr(e.message))
                          }
                        >
                          Acknowledgement slip
                        </button>
                      ) : null}
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="px-3 py-1 rounded bg-brand text-white text-xs disabled:opacity-50"
                      disabled={busy === course.course_id}
                      onClick={() => setPending(course)}
                    >
                      {text.action}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!data.courses.length ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-slate-500">
                  {text.empty}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      ) : null}
      {pending ? (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-lg max-w-md w-full p-5">
            <h2 className="text-base font-semibold text-[#0B2A4A]">Confirm application</h2>
            <p className="text-sm text-slate-600 mt-2">
              Are you sure you want to apply for {kind} in {pending.code} · {pending.name}?
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setPending(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-50"
                disabled={busy === pending.course_id}
                onClick={() => apply(pending)}
              >
                Yes, apply
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {slip ? <AckSlip slip={slip} onClose={() => setSlip(null)} /> : null}
    </div>
  );
}
