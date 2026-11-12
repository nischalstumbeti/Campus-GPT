"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Course = {
  course_code: string;
  course_name: string;
  current_attendance: number;
  remaining_classes: number;
  if_attend_all: number;
  can_miss: number;
  risk: string;
  cat_average: number | null;
  predicted_internal: number | null;
};

type Forecast = {
  summary: string;
  warnings?: string[];
  courses?: Course[];
  overall_attendance?: number;
  reading?: string;
};

function ForecastInner() {
  const [data, setData] = useState<Forecast | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    apiGet<Forecast>("/api/academic/forecast")
      .then((rows) => {
        setData(rows);
        setError("");
      })
      .catch((err) => {
        setData(null);
        setError(err instanceof Error ? err.message : "The forecast could not be loaded");
      });
  }, []);

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-5xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary mb-2">Attendance & marks forecast</h1>
        <p className="text-sm text-gray-600 mb-6">
          Built from your database records — how many classes you can still miss, and predicted internals.
        </p>
        {error ? <p className="text-sm text-rose-700 mb-4">{error}</p> : null}
        {!data && !error ? <p className="text-sm text-gray-500">Loading your attendance records…</p> : null}
        {data && (
          <>
            <p className="p-4 rounded-2xl bg-primary/5 text-primary mb-4">{data.summary}</p>
            {data.reading ? <p className="mb-4 whitespace-pre-wrap text-sm text-gray-700">{data.reading}</p> : null}
            {(data.warnings || []).length > 0 && (
              <ul className="mb-6 text-sm text-amber-800 list-disc pl-5">
                {(data.warnings || []).map((w) => <li key={w}>{w}</li>)}
              </ul>
            )}
            <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-primary/5 text-primary">
                  <tr>
                    <th className="p-3 text-left">Course</th>
                    <th className="p-3 text-left">Now</th>
                    <th className="p-3 text-left">If attend all</th>
                    <th className="p-3 text-left">Can miss</th>
                    <th className="p-3 text-left">Predicted internal</th>
                    <th className="p-3 text-left">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.courses || []).map((c) => (
                    <tr key={c.course_code} className="border-t border-gray-50">
                      <td className="p-3"><span className="font-medium">{c.course_code}</span><span className="block text-xs text-gray-500">{c.course_name}</span></td>
                      <td className="p-3">{c.current_attendance}%</td>
                      <td className="p-3">{c.if_attend_all}%</td>
                      <td className="p-3">{c.can_miss}</td>
                      <td className="p-3">{c.predicted_internal != null ? `${c.predicted_internal}%` : "—"}</td>
                      <td className={`p-3 font-semibold ${c.risk === "Critical" || c.risk === "High" ? "text-red-600" : c.risk === "Watch" ? "text-amber-700" : "text-green-700"}`}>{c.risk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
    </CopilotShell>
  );
}

export default function ForecastPage() {
  return <RequireAuth roles={["student"]}><ForecastInner /></RequireAuth>;
}
