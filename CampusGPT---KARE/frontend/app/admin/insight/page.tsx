"use client";

import { useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiPost } from "@/lib/api";

type Insight = {
  answer: string;
  thinking: string[];
  sources: { source?: string; excerpt?: string }[];
  measures: Record<string, number>;
  confidence: number;
  gemini: boolean;
};

const PROMPTS = [
  "Forecast attendance risk from the counted course rows. Say what is below 75 percent and what was not measured.",
  "What do the logged questions and the knowledge excerpts show that the office should check?",
  "Give a short campus reading using only the measured figures. Mark anything that is still unknown.",
];

function InsightInner() {
  const [question, setQuestion] = useState(PROMPTS[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Insight | null>(null);

  const ask = async (text: string) => {
    setBusy(true);
    setError("");
    try {
      const data = await apiPost<Insight>("/api/admin/insight", { question: text });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The desk could not answer");
    } finally {
      setBusy(false);
    }
  };

  return (
    <CopilotShell title="Thinking">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-xl font-bold text-primary">Thinking and forecast</h1>
          <p className="text-sm text-gray-600 mt-1">
            The desk counts attendance rows, logged questions, and knowledge excerpts, then asks Gemini to write only from that evidence. It refuses unethical requests and does not invent figures.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700"
              onClick={() => setQuestion(prompt)}
            >
              {prompt.slice(0, 42)}…
            </button>
          ))}
        </div>
        <form
          className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            ask(question);
          }}
        >
          <textarea
            required
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="min-h-28 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {busy ? "Checking records…" : "Ask from the records"}
          </button>
        </form>
        {error ? <p className="text-sm text-rose-700">{error}</p> : null}
        {result ? (
          <div className="space-y-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-800">Answer</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{result.answer}</p>
              <p className="mt-2 text-xs text-slate-500">
                {result.gemini ? "Written with Gemini." : "Gemini key is not saved yet."} Confidence {Math.round((result.confidence || 0) * 100)}%.
              </p>
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-800">Thinking</h2>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
                {result.thinking.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-800">Counted</h2>
              <ul className="mt-2 grid gap-1 text-sm text-slate-700 sm:grid-cols-2">
                {Object.entries(result.measures || {}).map(([key, value]) => (
                  <li key={key}>
                    {key.replaceAll("_", " ")}: {value}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        ) : null}
      </div>
    </CopilotShell>
  );
}

export default function InsightPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <InsightInner />
    </RequireAuth>
  );
}
