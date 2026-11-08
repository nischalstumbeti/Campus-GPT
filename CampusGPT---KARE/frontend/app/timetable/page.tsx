"use client";

import { useEffect, useMemo, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { apiGet } from "@/lib/api";

type Slot = {
  day: string;
  start_time: string;
  end_time: string;
  course_code: string;
  course_name: string;
  faculty: string;
  room: string;
};

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function normDay(day: string) {
  const map: Record<string, string> = {
    mon: "Monday",
    monday: "Monday",
    tue: "Tuesday",
    tues: "Tuesday",
    tuesday: "Tuesday",
    wed: "Wednesday",
    wednesday: "Wednesday",
    thu: "Thursday",
    thur: "Thursday",
    thurs: "Thursday",
    thursday: "Thursday",
    fri: "Friday",
    friday: "Friday",
    sat: "Saturday",
    saturday: "Saturday",
    sun: "Sunday",
    sunday: "Sunday",
  };
  return map[(day || "").trim().toLowerCase()] || day;
}

function normTime(t: string) {
  const parts = (t || "").split(":");
  if (parts.length >= 2 && !Number.isNaN(Number(parts[0])) && !Number.isNaN(Number(parts[1]))) {
    return `${String(Number(parts[0])).padStart(2, "0")}:${String(Number(parts[1])).padStart(2, "0")}`;
  }
  return t || "";
}

export default function TimetablePage() {
  return (
    <RequireAuth roles={["student"]}>
      <TimetableInner />
    </RequireAuth>
  );
}

function TimetableInner() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [student, setStudent] = useState("");
  const [source, setSource] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setErr("");
    apiGet<{
      student?: { full_name: string; roll_no: string; section: string };
      slots: Slot[];
      source?: string;
      note?: string;
    }>("/api/academic/timetable")
      .then((d) => {
        const normalized = (d.slots || []).map((s) => ({
          ...s,
          day: normDay(s.day),
          start_time: normTime(s.start_time),
          end_time: normTime(s.end_time),
        }));
        setSlots(normalized);
        setSource(d.source || "");
        setNote(d.note || "");
        if (d.student) {
          setStudent(`${d.student.full_name} · ${d.student.roll_no} · Sec ${d.student.section}`);
        }
      })
      .catch((e) => {
        setSlots([]);
        setErr(e instanceof Error ? e.message : "Could not load timetable from KARE UIS.");
      })
      .finally(() => setLoading(false));
  }, []);

  const activeDays = useMemo(() => {
    const present = new Set(slots.map((s) => s.day));
    const base = DAYS.filter((d) => present.has(d));
    return base.length ? base : DAYS.slice(0, 5);
  }, [slots]);

  const times = useMemo(() => Array.from(new Set(slots.map((s) => s.start_time).filter(Boolean))).sort(), [slots]);

  const cell = (day: string, time: string) => slots.find((s) => s.day === day && s.start_time === time);

  return (
    <CopilotShell title="Campus-GPT">
      <div className="min-h-full bg-white relative">
        <main className="max-w-6xl mx-auto px-4 py-8 relative z-10">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-primary">Class timetable</h1>
            <SyncBadge source={source} />
          </div>
          <p className="text-sm text-gray-600 mb-2">
            {loading ? "Loading from KARE UIS…" : student || "Your class schedule"}
          </p>
          {note && <p className="text-xs text-amber-700 mb-3">{note}</p>}
          {err && (
            <p className="text-sm text-red-600 mb-4 rounded-lg bg-red-50 border border-red-100 px-3 py-2">{err}</p>
          )}
          {!loading && !err && !slots.length && (
            <div className="rounded-2xl border border-dashed border-gray-200 p-8 text-center mb-4">
              <p className="text-sm font-medium text-gray-700">No class slots yet</p>
              <p className="text-xs text-gray-500 mt-2">
                This page uses the same KARE UIS timetable as chat. Ask your department to enroll you in course
                offerings, or enable Academic Timetable consent in Privacy.
              </p>
            </div>
          )}
          <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-primary/5 text-primary">
                  <th className="p-3 text-left">Time</th>
                  {activeDays.map((d) => (
                    <th key={d} className="p-3 text-left">
                      {d.slice(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {times.map((t) => (
                  <tr key={t} className="border-t border-gray-50">
                    <td className="p-3 font-medium text-gray-700 whitespace-nowrap">{t}</td>
                    {activeDays.map((d) => {
                      const s = cell(d, t);
                      return (
                        <td key={d} className="p-2 align-top">
                          {s ? (
                            <div className="rounded-lg bg-primary/5 p-2">
                              <p className="font-semibold text-primary">{s.course_code}</p>
                              <p className="text-xs text-gray-600">{s.course_name}</p>
                              <p className="text-[11px] text-gray-500">
                                {s.room} · {s.faculty}
                              </p>
                              <p className="text-[11px] text-gray-400">
                                {s.start_time}–{s.end_time}
                              </p>
                            </div>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!!slots.length && (
            <div className="mt-6 space-y-2">
              <h2 className="text-sm font-semibold text-gray-800">All slots</h2>
              <ul className="text-sm text-gray-700 space-y-1">
                {slots.map((s, i) => (
                  <li key={`${s.day}-${s.start_time}-${s.course_code}-${i}`}>
                    {s.day} {s.start_time}–{s.end_time}: {s.course_code} {s.course_name} ({s.room}
                    {s.faculty ? ` · ${s.faculty}` : ""})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </main>
      </div>
    </CopilotShell>
  );
}
