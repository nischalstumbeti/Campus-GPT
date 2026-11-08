"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

function CareerInner() {
  const [data, setData] = useState<{ disclaimer: string; strengths: string[]; gaps: string[]; next_steps: string[]; resume_blurb: string } | null>(null);
  useEffect(() => {
    apiGet<{ disclaimer: string; strengths: string[]; gaps: string[]; next_steps: string[]; resume_blurb: string }>("/api/copilot/career")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  return (
    <CopilotShell title="Career">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">Career assistant</h1>
        {data && (
          <>
            <p className="text-xs text-gray-500 mt-2">{data.disclaimer}</p>
            <p className="text-sm text-gray-700 mt-4">{data.resume_blurb}</p>
            <h2 className="font-semibold text-primary mt-6">Strengths</h2>
            <ul className="list-disc pl-5 text-sm">{data.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            <h2 className="font-semibold text-primary mt-4">Skill gaps</h2>
            <ul className="list-disc pl-5 text-sm">{data.gaps.map((s) => <li key={s}>{s}</li>)}</ul>
            <h2 className="font-semibold text-primary mt-4">Next steps</h2>
            <ul className="list-disc pl-5 text-sm">{data.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
          </>
        )}
      </main>
    </CopilotShell>
  );
}

export default function CareerPage() {
  return <RequireAuth roles={["student"]}><CareerInner /></RequireAuth>;
}
