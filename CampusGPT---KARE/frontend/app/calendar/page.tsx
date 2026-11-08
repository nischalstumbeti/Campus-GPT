"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Item = {
  kind: string;
  title: string;
  date: string;
  end_date: string;
  event_type: string;
  description: string;
  recurrence?: string;
};

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function parseISODate(value?: string | null) {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

function ymd(d: Date) {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function startOfDay(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function daysBetween(a: Date, b: Date) {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / 86400000);
}

function sameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function expandItems(items: Item[], rangeStart: Date, rangeEnd: Date): Item[] {
  const out: Item[] = [];
  for (const it of items) {
    if (!it.date) continue;
    if ((it.recurrence || "").toLowerCase() === "weekly") {
      const start = parseISODate(it.date);
      if (!start) continue;
      let cursor = new Date(start);
      while (cursor < rangeStart) cursor = addDays(cursor, 7);
      while (cursor <= rangeEnd) {
        out.push({ ...it, date: ymd(cursor), end_date: ymd(cursor) });
        cursor = addDays(cursor, 7);
      }
      continue;
    }
    out.push(it);
  }
  return out;
}

function itemsOnDay(items: Item[], day: Date) {
  const t = startOfDay(day).getTime();
  return items.filter((it) => {
    const start = parseISODate(it.date);
    if (!start) return false;
    const end = parseISODate(it.end_date) || start;
    return t >= startOfDay(start).getTime() && t <= startOfDay(end).getTime();
  });
}

function chipClass(it: Item) {
  if (it.kind === "task") return "bg-amber-100 text-amber-800";
  if (it.kind === "leave") return "bg-sky-100 text-sky-800";
  const t = (it.event_type || "").toLowerCase();
  if (t === "exam") return "bg-rose-100 text-rose-800";
  if (t === "holiday") return "bg-emerald-100 text-emerald-800";
  if (t === "deadline") return "bg-orange-100 text-orange-800";
  if (t === "meeting") return "bg-primary/15 text-primary";
  if (t === "notice") return "bg-gray-100 text-gray-700";
  return "bg-violet-100 text-violet-800";
}

function dayTone(dayItems: Item[]) {
  if (dayItems.some((i) => i.event_type === "holiday")) return "bg-emerald-50/80";
  if (dayItems.some((i) => i.event_type === "exam")) return "bg-rose-50/70";
  if (dayItems.some((i) => i.kind === "leave")) return "bg-sky-50/80";
  if (dayItems.some((i) => (parseISODate(i.end_date) && parseISODate(i.date) && daysBetween(parseISODate(i.date)!, parseISODate(i.end_date)!) > 10))) {
    return "bg-violet-50/50";
  }
  return "bg-white";
}

function CalendarInner() {
  const today = startOfDay(new Date());
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [selected, setSelected] = useState<Date>(today);
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    apiGet<{ items: Item[] }>("/api/me/calendar")
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]));
  }, []);

  const year = cursor.getFullYear();
  const month = cursor.getMonth();

  const grid = useMemo(() => {
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const weeks = Math.ceil((first.getDay() + last.getDate()) / 7);
    const start = addDays(first, -first.getDay());
    const cells: Date[] = [];
    for (let i = 0; i < weeks * 7; i++) cells.push(addDays(start, i));
    return cells;
  }, [year, month]);

  const visible = useMemo(() => {
    const rangeStart = grid[0];
    const rangeEnd = grid[grid.length - 1];
    return expandItems(items, rangeStart, rangeEnd);
  }, [items, grid]);

  const selectedItems = itemsOnDay(visible, selected);

  const monthItems = visible.filter((it) => {
    const start = parseISODate(it.date);
    const end = parseISODate(it.end_date) || start;
    if (!start) return false;
    const monthStart = new Date(year, month, 1);
    const monthEnd = new Date(year, month + 1, 0);
    return startOfDay(end!).getTime() >= monthStart.getTime() && startOfDay(start).getTime() <= monthEnd.getTime();
  });

  const weekCount = grid.length / 7;

  return (
    <CopilotShell title="Planner" fill>
      <div className="h-full bg-white relative flex flex-col overflow-hidden">
      <main className="flex-1 min-h-0 max-w-6xl w-full mx-auto px-3 py-2 relative z-10 flex flex-col gap-2">
        <div className="shrink-0 flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-bold text-primary">Calendar</h1>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setCursor(new Date(year, month - 1, 1))}
              className="p-1.5 rounded-lg border border-gray-200 bg-white hover:bg-primary/5 text-primary"
              aria-label="Previous month"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <p className="min-w-[140px] text-center text-sm font-semibold text-gray-900">
              {MONTHS[month]} {year}
            </p>
            <button
              type="button"
              onClick={() => setCursor(new Date(year, month + 1, 1))}
              className="p-1.5 rounded-lg border border-gray-200 bg-white hover:bg-primary/5 text-primary"
              aria-label="Next month"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => {
                setCursor(new Date(today.getFullYear(), today.getMonth(), 1));
                setSelected(today);
              }}
              className="ml-1 px-2.5 py-1.5 rounded-lg bg-primary text-white text-xs font-medium"
            >
              Today
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 grid grid-rows-[minmax(0,1fr)_min(32vh,220px)] lg:grid-rows-1 lg:grid-cols-[minmax(0,1fr)_220px] gap-2">
          <div className="min-h-0 rounded-xl border border-[#7C5AED]/15 bg-white shadow-sm overflow-hidden flex flex-col">
            <div className="grid grid-cols-7 shrink-0 border-b border-gray-100 bg-primary/5">
              {WEEKDAYS.map((d) => (
                <div key={d} className="py-1 text-center text-[11px] font-semibold text-primary tracking-wide">
                  <span className="sm:hidden">{d[0]}</span>
                  <span className="hidden sm:inline">{d}</span>
                </div>
              ))}
            </div>
            <div
              className="flex-1 min-h-0 grid grid-cols-7"
              style={{ gridTemplateRows: `repeat(${weekCount}, minmax(0, 1fr))` }}
            >
              {grid.map((day) => {
                const inMonth = day.getMonth() === month;
                const isToday = sameDay(day, today);
                const isSelected = sameDay(day, selected);
                const dayItems = itemsOnDay(visible, day);
                const long = dayItems.filter((i) => {
                  const s = parseISODate(i.date);
                  const e = parseISODate(i.end_date) || s;
                  return s && e && daysBetween(s, e) > 10;
                });
                const shortItems = dayItems.filter((i) => !long.includes(i));
                const chips = shortItems.slice(0, 2);
                const extra = shortItems.length - chips.length;
                return (
                  <button
                    key={ymd(day)}
                    type="button"
                    onClick={() => {
                      setSelected(day);
                      if (!inMonth) setCursor(new Date(day.getFullYear(), day.getMonth(), 1));
                    }}
                    className={`min-h-0 overflow-hidden p-1 text-left border-t border-r border-gray-100 ${dayTone(dayItems)} ${
                      !inMonth ? "opacity-40" : ""
                    } ${isSelected ? "ring-2 ring-inset ring-primary" : "hover:bg-primary/5"}`}
                  >
                    <span
                      className={`inline-flex w-6 h-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                        isToday ? "bg-primary text-white" : "text-gray-800"
                      }`}
                    >
                      {day.getDate()}
                    </span>
                    <div className="mt-0.5 space-y-0.5 hidden sm:block">
                      {chips.map((it, i) => (
                        <p key={`${it.title}-${i}`} className={`truncate px-1 py-px rounded text-[9px] font-medium leading-tight ${chipClass(it)}`}>
                          {it.title}
                        </p>
                      ))}
                      {extra > 0 && <p className="text-[9px] text-gray-500 px-1">+{extra}</p>}
                    </div>
                    {shortItems.length > 0 && (
                      <div className="sm:hidden mt-0.5 flex gap-0.5 flex-wrap">
                        {shortItems.slice(0, 3).map((it, i) => (
                          <span key={`${it.title}-${i}`} className={`w-1.5 h-1.5 rounded-full ${chipClass(it).split(" ")[0]}`} />
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="min-h-0 rounded-xl border border-[#7C5AED]/15 bg-white shadow-sm p-3 overflow-y-auto">
            <p className="text-[10px] uppercase tracking-wide text-gray-500">Selected day</p>
            <h2 className="text-sm font-semibold text-primary">
              {selected.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}
            </h2>
            <div className="mt-2 space-y-1.5">
              {selectedItems.length === 0 && (
                <p className="text-xs text-gray-500">No events on this day.</p>
              )}
              {selectedItems.map((it, i) => (
                <div key={`${it.title}-${i}`} className="rounded-lg border border-gray-100 p-2">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-semibold text-gray-900 leading-snug">{it.title}</p>
                    <span className={`shrink-0 text-[9px] px-1.5 py-0.5 rounded-full capitalize ${chipClass(it)}`}>
                      {it.kind === "academic" ? it.event_type : it.kind}
                    </span>
                  </div>
                  {it.description && <p className="text-[11px] text-gray-600 mt-0.5 line-clamp-2">{it.description}</p>}
                </div>
              ))}
            </div>
            <div className="mt-3 pt-2 border-t border-gray-100">
              <p className="text-[11px] text-gray-600">{monthItems.length} this month</p>
              <div className="mt-1.5 flex flex-wrap gap-1 text-[9px]">
                <span className="px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-800">Exam</span>
                <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800">Holiday</span>
                <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800">Task</span>
                <span className="px-1.5 py-0.5 rounded-full bg-sky-100 text-sky-800">Leave</span>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}

export default function CalendarPage() {
  return (
    <RequireAuth>
      <CalendarInner />
    </RequireAuth>
  );
}
