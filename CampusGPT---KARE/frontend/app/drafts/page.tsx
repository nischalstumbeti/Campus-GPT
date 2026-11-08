"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";

type Draft = { title: string; draft_type: string; body: string; recurrence: string };

export default function DraftsPage() {
  return (
    <RequireAuth roles={["faculty", "admin", "super_admin"]}>
      <DraftsInner />
    </RequireAuth>
  );
}

function DraftsInner() {
  const [types, setTypes] = useState<Record<string, string>>({});
  const [draftType, setDraftType] = useState("weekly_timetable");
  const [extra, setExtra] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiGet<{ types: Record<string, string> }>("/api/academic/draft-types")
      .then((d) => setTypes(d.types || {}))
      .catch(() => setTypes({}));
  }, []);

  const generate = async (save = false) => {
    const res = await apiPost<{ draft: Draft }>("/api/academic/drafts", {
      draft_type: draftType,
      extra,
      save,
    });
    setDraft(res.draft);
    setCopied(false);
  };

  const copy = async () => {
    if (!draft?.body) return;
    await navigator.clipboard.writeText(draft.body);
    setCopied(true);
  };

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-4xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary">Draft recurring circulars</h1>
        <p className="text-sm text-gray-600 mb-6">
          Build weekly reminders, faculty meeting invites, attendance notices, and exam circulars from live timetable and calendar data.
        </p>
        <div className="grid gap-3 mb-4">
          <select
            value={draftType}
            onChange={(e) => setDraftType(e.target.value)}
            className="rounded-xl border border-gray-200 px-3 py-2.5 bg-white"
          >
            {Object.entries(types).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <textarea
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            rows={3}
            placeholder="Optional extra instruction, e.g. include Saturday extra class in LH-201"
            className="rounded-xl border border-gray-200 px-3 py-2.5"
          />
          <div className="flex gap-3">
            <button onClick={() => generate(false)} className="px-4 py-2 rounded-xl bg-primary text-white font-medium">
              Generate draft
            </button>
            <button onClick={() => generate(true)} className="px-4 py-2 rounded-xl border border-primary text-primary font-medium">
              Generate & save
            </button>
          </div>
        </div>
        {draft && (
          <div className="rounded-2xl border border-gray-100 bg-white p-5">
            <div className="flex justify-between items-start gap-3 mb-3">
              <div>
                <h2 className="font-semibold text-primary">{draft.title}</h2>
                <p className="text-xs text-gray-500">Recurrence: {draft.recurrence}</p>
              </div>
              <button onClick={copy} className="text-sm text-primary font-medium">
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans">{draft.body}</pre>
          </div>
        )}
      </main>
    </div>
    </CopilotShell>
  );
}
