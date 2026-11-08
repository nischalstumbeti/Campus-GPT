"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Row = {
  faculty: string;
  designation: string;
  department: string;
  cabin: string;
  email: string;
  day: string;
  start_time: string;
  end_time: string;
  kind: string;
  location: string;
  notes: string;
};

export default function FacultyPage() {
  return (
    <RequireAuth>
      <FacultyInner />
    </RequireAuth>
  );
}

function FacultyInner() {
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState("");

  const load = (query = "") => {
    const path = query ? `/api/academic/faculty?q=${encodeURIComponent(query)}` : "/api/academic/faculty";
    apiGet<{ records: Row[] }>(path).then((d) => setRows(d.records || [])).catch(() => setRows([]));
  };

  useEffect(() => { load(); }, []);

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-5xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary">Faculty availability</h1>
        <p className="text-sm text-gray-600 mb-4">Office hours and teaching slots from KARE UIS</p>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(q)}
          placeholder="Search faculty name..."
          className="mb-6 w-full max-w-md rounded-xl border border-gray-200 px-4 py-2.5"
        />
        <div className="grid md:grid-cols-2 gap-4">
          {rows.map((r, i) => (
            <div key={i} className="p-4 rounded-2xl border border-gray-100 bg-white">
              <div className="flex justify-between">
                <div>
                  <p className="font-semibold text-primary">{r.faculty}</p>
                  <p className="text-xs text-gray-500">{r.designation} · {r.department} · {r.cabin}</p>
                </div>
                <span className={`text-[11px] px-2 py-1 rounded-full ${r.kind === "office_hours" ? "bg-green-50 text-green-700" : r.kind === "class" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>
                  {(r.kind || "slot").replace("_", " ")}
                </span>
              </div>
              <p className="mt-2 text-sm">{r.day} {r.start_time}–{r.end_time} · {r.location}</p>
              <p className="text-xs text-gray-500 mt-1">{r.notes}</p>
              <p className="text-xs text-gray-400 mt-1">{r.email}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}
