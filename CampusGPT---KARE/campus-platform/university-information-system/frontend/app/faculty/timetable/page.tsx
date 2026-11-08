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
  section?: string;
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

function startOf(slot: Slot) {
  return slot.start_time || slot.start || "";
}

function endOf(slot: Slot) {
  return slot.end_time || slot.end || "";
}

const COURSE_COLORS = ["#dbeafe", "#dcfce7", "#fce7f3", "#fef3c7", "#e0e7ff", "#ffedd5", "#ccfbf1", "#fee2e2", "#ede9fe", "#ecfccb"];

function courseColor(code: string) {
  let total = 0;
  for (const char of code || "") total += char.charCodeAt(0);
  return COURSE_COLORS[total % COURSE_COLORS.length];
}

export default function FacultyTimetablePage() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [facultyId, setFacultyId] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ faculty_id?: string; name?: string; slots: Slot[] }>("/api/v1/faculty/timetable")
      .then((data) => {
        setSlots(data.slots || []);
        setFacultyId(data.faculty_id || "");
        setName(data.name || "");
      })
      .catch((e) => setErr(e.message));
  }, []);

  const times = useMemo(() => Array.from(new Set(slots.map(startOf).filter(Boolean))).sort(), [slots]);
  const cell = (day: string, time: string) => slots.find((slot) => fullDay(slot.day) === day && startOf(slot) === time);

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">My Class Time Table</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b border-slate-200">
          {name || facultyId ? `${name}${facultyId ? ` · ${facultyId}` : ""}` : "Loading…"} — classes allocated to you
        </p>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="uis-table-head">
              <tr>
                <th className="p-3 text-left">Time</th>
                {DAYS.map((day) => (
                  <th key={day} className="p-3 text-left">
                    {day.slice(0, 3)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {times.length === 0 ? (
                <tr>
                  <td className="p-4 text-slate-500" colSpan={6}>
                    No class slots are allocated yet.
                  </td>
                </tr>
              ) : (
                times.map((time) => (
                  <tr key={time} className="border-t border-slate-200">
                    <td className="p-3 font-medium text-slate-700 whitespace-nowrap bg-slate-50">{time}</td>
                    {DAYS.map((day) => {
                      const slot = cell(day, time);
                      return (
                        <td key={day} className="p-2 align-top">
                          {slot ? (
                            <div className="rounded-lg border border-black/5 p-2" style={{ backgroundColor: courseColor(slot.course_code || slot.code || "") }}>
                              <p className="font-semibold text-[#0B2A4A]">{slot.course_code || slot.code}</p>
                              <p className="text-xs text-slate-600">{slot.course_name || slot.course}</p>
                              <p className="text-[11px] text-slate-500">
                                {slot.room}
                                {slot.section ? ` · Section ${slot.section}` : ""}
                              </p>
                              <p className="text-[11px] text-slate-400">
                                {startOf(slot)}–{endOf(slot)}
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
      </section>
    </AppShell>
  );
}
