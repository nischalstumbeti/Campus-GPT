"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";

type Latency = { avg: number | null; min: number | null; max: number | null; median: number | null };

type EvalResult = {
  ok?: boolean;
  run_id?: number;
  created_at?: string;
  suite_name?: string;
  case_count?: number;
  latency_ms?: Latency;
  keyword_accuracy?: number | null;
  token_f1?: number | null;
  retrieval_hit_at_k?: number | null;
  escalate_rate?: number | null;
  notes?: string;
  disclaimer?: string;
  metric_definitions?: Record<string, string>;
  cases?: {
    case_id: string;
    query: string;
    agent_type: string;
    latency_ms: number;
    keyword_hit_rate: number;
    token_f1: number;
    retrieval_hit: boolean;
    escalated: boolean;
    answer_preview: string;
  }[];
  detail?: string;
};

function pct(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function ms(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(0)} ms`;
}

function EvalInner() {
  const [latest, setLatest] = useState<EvalResult | null>(null);
  const [liveLatency, setLiveLatency] = useState<{ sample_size: number; latency_ms: Latency; note?: string } | null>(
    null
  );
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    try {
      const d = await apiGet<EvalResult>("/api/admin/eval/latest");
      setLatest(d);
    } catch {
      setLatest(null);
    }
    try {
      const l = await apiGet<{ sample_size: number; latency_ms: Latency; note?: string }>(
        "/api/admin/eval/latency"
      );
      setLiveLatency(l);
    } catch {
      setLiveLatency(null);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runEval = async () => {
    setRunning(true);
    setMsg("Running gold suite… this can take 1–3 minutes.");
    try {
      const d = await apiPost<EvalResult>("/api/admin/eval/run", {});
      setLatest({ ok: true, ...d });
      setMsg(
        `Done. Keyword accuracy ${pct(d.keyword_accuracy)}, token F1 ${pct(d.token_f1)}, latency avg ${ms(
          d.latency_ms?.avg
        )}.`
      );
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setRunning(false);
    }
  };

  const lat = latest?.latency_ms;

  return (
    <CopilotShell title="Evaluation">
      <div className="max-w-5xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-primary">Model evaluation</h1>
        <p className="text-sm text-gray-600 mt-1">
          Measures real latency and automatic answer proxies on a gold FAQ suite. These are{" "}
          <strong>not</strong> human-rated accuracy or IR Precision@K unless separately annotated.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runEval}
            disabled={running}
            className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-60"
          >
            {running ? "Running evaluation…" : "Run gold evaluation"}
          </button>
          <button
            type="button"
            onClick={load}
            className="px-4 py-2 rounded-lg border border-slate-200 text-sm"
          >
            Refresh
          </button>
        </div>
        {msg && <p className="mt-2 text-sm text-slate-700">{msg}</p>}

        <div className="mt-6 grid md:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Gold-suite latency</p>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div>Avg: <strong>{ms(lat?.avg)}</strong></div>
              <div>Median: <strong>{ms(lat?.median)}</strong></div>
              <div>Min: <strong>{ms(lat?.min)}</strong></div>
              <div>Max: <strong>{ms(lat?.max)}</strong></div>
            </dl>
            <p className="text-xs text-slate-500 mt-2">
              Run #{latest?.run_id ?? "—"} · {latest?.case_count ?? 0} cases · {latest?.suite_name || "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Answer / retrieval proxies</p>
            <dl className="mt-2 space-y-1 text-sm">
              <div>
                Keyword accuracy: <strong>{pct(latest?.keyword_accuracy)}</strong>
              </div>
              <div>
                Token F1 vs reference: <strong>{pct(latest?.token_f1)}</strong>
              </div>
              <div>
                Retrieval hit@k (keyword-in-sources): <strong>{pct(latest?.retrieval_hit_at_k)}</strong>
              </div>
              <div>
                Escalate rate: <strong>{pct(latest?.escalate_rate)}</strong>
              </div>
            </dl>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">Live traffic latency (query_logs)</p>
          <p className="text-sm mt-1">
            n={liveLatency?.sample_size ?? 0} · avg {ms(liveLatency?.latency_ms?.avg)} · median{" "}
            {ms(liveLatency?.latency_ms?.median)} · min {ms(liveLatency?.latency_ms?.min)} · max{" "}
            {ms(liveLatency?.latency_ms?.max)}
          </p>
          <p className="text-xs text-slate-500 mt-1">{liveLatency?.note}</p>
        </div>

        {(latest?.notes || latest?.disclaimer) && (
          <p className="mt-4 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
            {latest.notes || latest.disclaimer}
          </p>
        )}

        {latest?.cases && latest.cases.length > 0 && (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white overflow-hidden">
            <div className="px-4 py-3 border-b text-sm font-semibold text-primary">Per-case results</div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-left">
                  <tr>
                    <th className="px-3 py-2">ID</th>
                    <th className="px-3 py-2">Agent</th>
                    <th className="px-3 py-2">Latency</th>
                    <th className="px-3 py-2">KW</th>
                    <th className="px-3 py-2">F1</th>
                    <th className="px-3 py-2">Ret</th>
                    <th className="px-3 py-2">Query</th>
                  </tr>
                </thead>
                <tbody>
                  {latest.cases.map((c) => (
                    <tr key={c.case_id} className="border-t border-slate-100 align-top">
                      <td className="px-3 py-2 font-mono">{c.case_id}</td>
                      <td className="px-3 py-2">{c.agent_type}</td>
                      <td className="px-3 py-2">{ms(c.latency_ms)}</td>
                      <td className="px-3 py-2">{pct(c.keyword_hit_rate)}</td>
                      <td className="px-3 py-2">{pct(c.token_f1)}</td>
                      <td className="px-3 py-2">{c.retrieval_hit ? "yes" : "no"}</td>
                      <td className="px-3 py-2 max-w-xs truncate" title={c.query}>
                        {c.query}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </CopilotShell>
  );
}

export default function EvaluationPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <EvalInner />
    </RequireAuth>
  );
}
