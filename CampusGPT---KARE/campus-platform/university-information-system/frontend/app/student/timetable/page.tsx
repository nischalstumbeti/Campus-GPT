"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Slot = {
  day: string;
  start?: string;
  end?: string;
  start_time?: string;
  end_time?: string;
  course?: string;
  course_name?: string;
  code?: string;
  course_code?: string;
  faculty?: string;
  room?: string;
};

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const DAY_FULL: Record<string, string> = {
  Mon: "Monday",
  Tue: "Tuesday",
  Wed: "Wednesday",
  Thu: "Thursday",
  Fri: "Friday",
  Sat: "Saturday",
  Sun: "Sunday",
};

function fullDay(day: string) {
  return DAY_FULL[day] || day;
}

function startOf(s: Slot) {
  return s.start_time || s.start || "";
}

function endOf(s: Slot) {
  return s.end_time || s.end || "";
}

const COURSE_COLORS = ["#dbeafe", "#dcfce7", "#fce7f3", "#fef3c7", "#e0e7ff", "#ffedd5", "#ccfbf1", "#fee2e2", "#ede9fe", "#ecfccb"];

function courseColor(code: string) {
  let total = 0;
  for (const char of code || "") total += char.charCodeAt(0);
  return COURSE_COLORS[total % COURSE_COLORS.length];
}

export default function TimetablePage() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [studentId, setStudentId] = useState("");
  const [section, setSection] = useState("");
  const [semester, setSemester] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<{ student_id?: string; section?: string; semester?: number; slots: Slot[] }>("/api/v1/student/timetable").then((d) => {
      setSlots(d.slots || []);
      setStudentId(d.student_id || "");
      setSection(d.section || "");
      setSemester(d.semester ?? null);
    });
  }, []);

  const times = useMemo(() => Array.from(new Set(slots.map(startOf).filter(Boolean))).sort(), [slots]);
  const cell = (day: string, time: string) =>
    slots.find((s) => fullDay(s.day) === day && startOf(s) === time);

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-1">Class timetable</h1>
      <p className="text-sm text-slate-500 mb-4">
        {studentId
          ? `Roll ${studentId}${semester ? ` · Semester ${semester}` : ""}${section ? ` · Section ${section}` : ""}`
          : "Loading…"}{" "}
        — times and rooms are the ones saved by the administrator
      </p>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-brand">
              <th className="p-3 text-left">Time</th>
              {DAYS.map((d) => (
                <th key={d} className="p-3 text-left">
                  {d.slice(0, 3)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {times.length === 0 ? (
              <tr>
                <td className="p-4 text-slate-400" colSpan={6}>
                  No timetable slots yet.
                </td>
              </tr>
            ) : (
              times.map((t) => (
                <tr key={t} className="border-t border-slate-100">
                  <td className="p-3 font-medium text-slate-700 whitespace-nowrap">{t}</td>
                  {DAYS.map((d) => {
                    const s = cell(d, t);
                    return (
                      <td key={d} className="p-2 align-top">
                        {s ? (
                          <div className="rounded-lg p-2 border border-black/5" style={{ backgroundColor: courseColor(s.course_code || s.code || "") }}>
                            <p className="font-semibold text-[#0B2A4A]">{s.course_code || s.code}</p>
                            <p className="text-xs text-slate-600">{s.course_name || s.course}</p>
                            <p className="text-[11px] text-slate-500">
                              {s.room}
                              {s.faculty ? ` · ${s.faculty}` : ""}
                            </p>
                            <p className="text-[11px] text-slate-400">
                              {startOf(s)}–{endOf(s)}
                            </p>
                          </div>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {Array.from(new Map(slots.map((slot) => [slot.course_code || slot.code || "", slot])).values())
          .filter((slot) => slot.course_code || slot.code)
          .map((slot) => {
            const code = slot.course_code || slot.code || "";
            return (
              <span key={code} className="inline-flex items-center gap-2 rounded border border-black/5 px-2 py-1 text-xs" style={{ backgroundColor: courseColor(code) }}>
                <strong>{code}</strong> {slot.course_name || slot.course}
              </span>
            );
          })}
      </div>
    </AppShell>
  );
}
