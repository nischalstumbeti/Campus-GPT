"use client";

import { useEffect, useState } from "react";
import AckSlip from "@/components/AckSlip";
import { apiFetch } from "@/lib/api";

type Course = {
  offering_id: number;
  code: string;
  name: string;
  credits: number;
  section: string;
  faculty: string;
  enrolled: boolean;
};

type RequestRow = {
  id: number;
  status: string;
  advisor_status: string;
  hod_status: string;
  courses: { code: string; name: string }[];
  slip: boolean;
};

type Payload = {
  enabled: boolean;
  note: string;
  courses: Course[];
  request: RequestRow | null;
};

const COPY = {
  registration: {
    closed: "Course registration is closed. You can register after an administrator opens it.",
    title: "Courses mapped for this semester",
  },
  withdrawal: {
    closed: "Course withdrawal is closed. You can apply after an administrator opens it.",
    title: "Courses you can withdraw",
  },
};

function stage(request: RequestRow) {
  if (request.status === "approved") return "Approved by the faculty advisor and the HoD.";
  if (request.status === "rejected") return "This request was not approved.";
  if (request.advisor_status === "approved") return "Faculty advisor approved. Waiting for the Head of Department.";
  return "Submitted. Waiting for the faculty advisor.";
}

export default function CourseRegister({ kind }: { kind: "registration" | "withdrawal" }) {
  const [data, setData] = useState<Payload | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [slip, setSlip] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const text = COPY[kind];

  const load = () => {
    apiFetch<Payload>(`/api/v1/student/registration?kind=${kind}`)
      .then(setData)
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    setErr("");
    setData(null);
    setPicked([]);
    load();
  }, [kind]);

  const locked = Boolean(data?.request && data.request.status !== "rejected");
  const selectable = (data?.courses || []).filter((course) => (kind === "withdrawal" ? true : !course.enrolled));

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      await apiFetch(`/api/v1/student/registration?kind=${kind}`, {
        method: "POST",
        body: JSON.stringify({ offering_ids: picked }),
      });
      setConfirming(false);
      setPicked([]);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not submit");
    } finally {
      setBusy(false);
    }
  };

  const openSlip = async () => {
    if (!data?.request) return;
    const row = await apiFetch(`/api/v1/student/slips/registration/${data.request.id}`);
    setSlip(row);
  };

  if (!data) {
    return err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : <p className="px-4 py-4 text-sm text-slate-500">Loading…</p>;
  }

  return (
    <div>
      <div className="px-4 py-3 text-sm border-b border-slate-100">
        <p className={data.enabled ? "text-emerald-700" : "text-slate-600"}>{data.enabled ? "Registration is open for your semester." : text.closed}</p>
        {data.note ? <p className="mt-1 text-slate-600">{data.note}</p> : null}
      </div>
      {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
      {data.request ? (
        <div className="px-4 py-3 text-sm border-b border-slate-100">
          <p>{stage(data.request)}</p>
          <p className="mt-1 text-slate-600">{data.request.courses.map((course) => course.code).join(", ")}</p>
          {data.request.slip ? (
            <button type="button" className="mt-2 text-brand font-medium underline" onClick={() => openSlip().catch((e) => setErr(e.message))}>
              View acknowledgement slip
            </button>
          ) : null}
        </div>
      ) : null}
      {data.enabled && !locked ? (
        <>
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left text-xs">
              <tr>
                <th className="px-3 py-2"></th>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Course</th>
                <th className="px-3 py-2">Section</th>
                <th className="px-3 py-2">Faculty</th>
                <th className="px-3 py-2">Credits</th>
              </tr>
            </thead>
            <tbody>
              {data.courses.map((course) => {
                const disabled = kind === "registration" && course.enrolled;
                return (
                  <tr key={course.offering_id} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        disabled={disabled}
                        checked={picked.includes(course.offering_id)}
                        onChange={(e) =>
                          setPicked((current) =>
                            e.target.checked ? [...current, course.offering_id] : current.filter((id) => id !== course.offering_id)
                          )
                        }
                      />
                    </td>
                    <td className="px-3 py-2 font-medium">{course.code}</td>
                    <td className="px-3 py-2">{course.name}</td>
                    <td className="px-3 py-2">{course.section}</td>
                    <td className="px-3 py-2">{course.faculty || "—"}</td>
                    <td className="px-3 py-2">{disabled ? "Enrolled" : course.credits}</td>
                  </tr>
                );
              })}
              {!data.courses.length ? (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-slate-500">
                    No mapped courses are open for this semester.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          <div className="px-4 py-3">
            <button
              type="button"
              className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-50"
              disabled={!picked.length || !selectable.length}
              onClick={() => setConfirming(true)}
            >
              Submit
            </button>
          </div>
        </>
      ) : null}
      {confirming ? (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-md p-5 shadow-lg">
            <h2 className="text-lg font-semibold text-brand">Confirm submission</h2>
            <p className="mt-2 text-sm text-slate-600">
              Submit these courses? A second review is required. The acknowledgement slip is issued after the faculty advisor and the Head of Department approve.
            </p>
            <ul className="mt-3 text-sm">
              {data.courses
                .filter((course) => picked.includes(course.offering_id))
                .map((course) => (
                  <li key={course.offering_id}>
                    {course.code} · {course.name}
                  </li>
                ))}
            </ul>
            <div className="mt-4 flex gap-2">
              <button type="button" className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-50" disabled={busy} onClick={submit}>
                Confirm
              </button>
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setConfirming(false)}>
                Back
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {slip ? <AckSlip slip={slip} onClose={() => setSlip(null)} /> : null}
    </div>
  );
}
