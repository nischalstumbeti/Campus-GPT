"use client";

import { useEffect, useState } from "react";
import { API, apiFetch, getToken } from "@/lib/api";

type Exam = { code: string; course: string; type: string; date: string; start: string; venue: string; attendance?: number };
type Held = { code: string; course: string; attendance: number; reason: string };
type Ticket = {
  enabled: boolean;
  min_attendance?: number;
  require_overall?: boolean;
  require_subject?: boolean;
  overall_attendance?: number;
  overall_ok?: boolean;
  institution?: string;
  title?: string;
  session_name?: string;
  instructions?: string;
  footer?: string;
  name?: string;
  student_id?: string;
  program?: string;
  batch?: string;
  semester?: number;
  section?: string;
  photo_url?: string;
  exams?: Exam[];
  withheld?: Held[];
  waiver?: { reason: string; recommended_by: string; source: string } | null;
};

async function fetchPdf() {
  const token = getToken();
  const res = await fetch(`${API}/api/v1/student/hall-ticket/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "Could not open the hall ticket");
  }
  return res.blob();
}

export default function HallTicket() {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    apiFetch<Ticket>("/api/v1/student/hall-ticket")
      .then(setTicket)
      .catch((e) => setErr(e.message));
  }, []);

  const openPdf = async (download: boolean) => {
    setBusy(download ? "download" : "view");
    setErr("");
    try {
      const blob = await fetchPdf();
      const url = URL.createObjectURL(blob);
      if (download) {
        const link = document.createElement("a");
        link.href = url;
        link.download = `hall-ticket-${ticket?.student_id || "student"}.pdf`;
        link.click();
      } else {
        window.open(url, "_blank", "noopener");
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not open the hall ticket");
    } finally {
      setBusy("");
    }
  };

  if (!ticket) {
    return err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : <p className="px-4 py-4 text-sm text-slate-500">Loading…</p>;
  }

  if (!ticket.enabled) {
    return (
      <p className="px-4 py-4 text-sm text-slate-600">
        The hall ticket is not available yet. You can view, print, and download it after an administrator enables it.
      </p>
    );
  }

  const minimum = ticket.min_attendance ?? 75;
  const canPrint = (ticket.exams || []).length > 0;

  return (
    <div>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .hall-sheet, .hall-sheet * { visibility: visible; }
          .hall-sheet { position: absolute; left: 0; top: 0; width: 100%; box-shadow: none; }
          .no-print { display: none !important; }
        }
      `}</style>
      <div className="no-print px-4 py-3 border-b border-slate-100 space-y-2">
        <p className="text-sm text-slate-600">
          Overall attendance {ticket.overall_attendance ?? 0}%. A subject is listed when attendance is {minimum}% or more
          {ticket.require_overall ? ", and overall attendance must also meet that mark" : ""}.
        </p>
        {ticket.waiver ? (
          <p className="text-sm text-[#0B2A4A]">
            Recommended by {ticket.waiver.source}: {ticket.waiver.recommended_by}. {ticket.waiver.reason}
          </p>
        ) : null}
        {canPrint ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" className="px-3 py-1.5 rounded bg-brand text-white text-sm disabled:opacity-50" disabled={busy === "view"} onClick={() => openPdf(false)}>
              View PDF
            </button>
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => window.print()}>
              Print
            </button>
            <button type="button" className="px-3 py-1.5 rounded border text-sm disabled:opacity-50" disabled={busy === "download"} onClick={() => openPdf(true)}>
              Download
            </button>
          </div>
        ) : (
          <p className="text-sm text-red-700">No subject meets the attendance rule, so the hall ticket cannot be printed.</p>
        )}
        {(ticket.withheld || []).length ? (
          <ul className="text-sm text-red-700 space-y-0.5">
            {(ticket.withheld || []).map((row) => (
              <li key={row.code}>{row.reason}</li>
            ))}
          </ul>
        ) : null}
      </div>
      {err ? <p className="px-4 py-2 text-sm text-red-600">{err}</p> : null}
      <article className="hall-sheet m-4 border border-slate-300 bg-white p-6">
        <div className="flex justify-between gap-4 border-b border-slate-300 pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{ticket.institution}</p>
            <h2 className="text-xl font-semibold text-brand">{ticket.title}</h2>
            {ticket.session_name ? <p className="text-sm text-slate-600">{ticket.session_name}</p> : null}
          </div>
          {ticket.photo_url ? (
            <img src={ticket.photo_url} alt="" className="h-20 w-16 object-cover border" />
          ) : (
            <div className="h-20 w-16 border border-dashed border-slate-300 text-[10px] text-slate-400 flex items-center justify-center text-center">
              Photo
            </div>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mt-4">
          <div><dt className="text-slate-500">Name</dt><dd>{ticket.name}</dd></div>
          <div><dt className="text-slate-500">Register number</dt><dd>{ticket.student_id}</dd></div>
          <div><dt className="text-slate-500">Programme</dt><dd>{ticket.program}</dd></div>
          <div><dt className="text-slate-500">Batch / Semester / Section</dt><dd>{ticket.batch} · {ticket.semester} · {ticket.section}</dd></div>
        </dl>
        <table className="w-full text-sm mt-4">
          <thead className="uis-table-head text-left text-xs">
            <tr>
              <th className="px-2 py-2">Course</th>
              <th className="px-2 py-2">Exam</th>
              <th className="px-2 py-2">Date</th>
              <th className="px-2 py-2">Time</th>
              <th className="px-2 py-2">Venue</th>
              <th className="px-2 py-2">Attendance</th>
            </tr>
          </thead>
          <tbody>
            {(ticket.exams || []).map((exam) => (
              <tr key={`${exam.code}-${exam.type}`} className="border-t border-slate-100">
                <td className="px-2 py-2">{exam.code} · {exam.course}</td>
                <td className="px-2 py-2">{exam.type}</td>
                <td className="px-2 py-2">{exam.date}</td>
                <td className="px-2 py-2">{exam.start}</td>
                <td className="px-2 py-2">{exam.venue}</td>
                <td className="px-2 py-2">{exam.attendance ?? "—"}%</td>
              </tr>
            ))}
            {!ticket.exams?.length ? (
              <tr><td colSpan={6} className="px-2 py-3 text-slate-500">No subject on this ticket meets the attendance rule.</td></tr>
            ) : null}
          </tbody>
        </table>
        {ticket.instructions ? (
          <div className="mt-4 text-sm whitespace-pre-line">
            <p className="font-medium text-slate-700">Instructions</p>
            <p className="text-slate-600 mt-1">{ticket.instructions}</p>
          </div>
        ) : null}
        {ticket.footer ? <p className="mt-4 text-xs text-slate-500">{ticket.footer}</p> : null}
        <div className="mt-10 flex justify-between text-xs text-slate-500">
          <span>Student signature</span>
          <span>Controller of Examinations</span>
        </div>
      </article>
    </div>
  );
}
