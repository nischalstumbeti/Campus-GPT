"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type State = "up" | "degraded" | "down" | "not_running";

type Service = {
  key: string;
  group: string;
  name: string;
  target: string;
  kind: "http" | "tcp" | "self";
  optional: boolean;
  note: string | null;
  state: State;
  latency_ms: number | null;
  detail: string;
  last_up: string | null;
  uptime_pct: number;
  history: { at: string; state: State; latency_ms: number | null }[];
};

type Report = {
  checked_at: string;
  summary: { total: number; up: number; degraded: number; down: number; overall: "up" | "degraded" | "down" };
  services: Service[];
};

const STATE_STYLE: Record<State, { label: string; dot: string; pill: string; bar: string }> = {
  up: { label: "Running", dot: "bg-emerald-500", pill: "bg-emerald-50 text-emerald-700 border-emerald-200", bar: "bg-emerald-500" },
  degraded: { label: "Degraded", dot: "bg-amber-500", pill: "bg-amber-50 text-amber-700 border-amber-200", bar: "bg-amber-400" },
  down: { label: "Down", dot: "bg-rose-500", pill: "bg-rose-50 text-rose-700 border-rose-200", bar: "bg-rose-500" },
  not_running: { label: "Not running", dot: "bg-slate-400", pill: "bg-slate-50 text-slate-600 border-slate-200", bar: "bg-slate-300" },
};

const OVERALL = {
  up: { text: "All services are running", cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  degraded: { text: "Some services are degraded", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  down: { text: "One or more services are down", cls: "border-rose-200 bg-rose-50 text-rose-800" },
};

const INTERVALS = [
  { value: 0, label: "Off" },
  { value: 15, label: "Every 15 s" },
  { value: 30, label: "Every 30 s" },
  { value: 60, label: "Every 1 min" },
];

function time(value: string | null) {
  return value ? new Date(value).toLocaleTimeString() : "—";
}

function latencyClass(ms: number | null) {
  if (ms === null) return "text-slate-400";
  if (ms < 300) return "text-emerald-700";
  if (ms < 1500) return "text-amber-700";
  return "text-rose-700";
}

export default function ServiceMonitorPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [interval, setIntervalSec] = useState(15);

  const check = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await apiFetch<Report>("/api/v1/admin/services/status"));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status check failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  useEffect(() => {
    if (!interval) return;
    const id = window.setInterval(check, interval * 1000);
    return () => window.clearInterval(id);
  }, [interval, check]);

  const groups = report
    ? report.services.reduce<Record<string, Service[]>>((acc, s) => {
        (acc[s.group] ||= []).push(s);
        return acc;
      }, {})
    : {};

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brand">Service monitor</h1>
          <p className="text-sm text-slate-500">
            Live checks run from the UIS API. Last checked {report ? time(report.checked_at) : "—"}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600" htmlFor="refresh">
            Auto refresh
          </label>
          <select
            id="refresh"
            className="rounded-md border px-2 py-1.5 text-sm"
            value={interval}
            onChange={(e) => setIntervalSec(Number(e.target.value))}
          >
            {INTERVALS.map((i) => (
              <option key={i.value} value={i.value}>
                {i.label}
              </option>
            ))}
          </select>
          <button
            onClick={check}
            disabled={loading}
            className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
          >
            {loading ? "Checking…" : "Check now"}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}

      {!report && !error && <div className="rounded-lg border bg-white p-6 text-sm text-slate-500">Checking services…</div>}

      {report && (
        <>
          <div className={`mb-4 rounded-lg border p-4 ${OVERALL[report.summary.overall].cls}`}>
            <p className="font-semibold">{OVERALL[report.summary.overall].text}</p>
            <p className="text-sm">
              {report.summary.up} of {report.summary.total} running
              {report.summary.degraded ? ` · ${report.summary.degraded} degraded` : ""}
              {report.summary.down ? ` · ${report.summary.down} down` : ""}
            </p>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "Monitored", value: report.summary.total, cls: "text-slate-900" },
              { label: "Running", value: report.summary.up, cls: "text-emerald-700" },
              { label: "Degraded", value: report.summary.degraded, cls: "text-amber-700" },
              { label: "Down", value: report.summary.down, cls: "text-rose-700" },
            ].map((c) => (
              <div key={c.label} className="rounded-lg border bg-white p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">{c.label}</p>
                <p className={`text-2xl font-bold ${c.cls}`}>{c.value}</p>
              </div>
            ))}
          </div>

          {Object.entries(groups).map(([group, services]) => (
            <section key={group} className="mb-6">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{group}</h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {services.map((s) => {
                  const st = STATE_STYLE[s.state];
                  return (
                    <div key={s.key} className="rounded-lg border bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${st.dot}`} />
                            <p className="font-semibold text-slate-900">{s.name}</p>
                          </div>
                          <p className="mt-0.5 truncate text-xs text-slate-500">
                            {s.kind === "http" && !s.target.includes("/health") && !s.target.includes("/api/") ? (
                              <a href={s.target} target="_blank" rel="noopener noreferrer" className="hover:underline">
                                {s.target}
                              </a>
                            ) : (
                              s.target
                            )}
                          </p>
                        </div>
                        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${st.pill}`}>{st.label}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{s.detail}</p>
                      {s.note && <p className="text-xs text-slate-500">{s.note}</p>}
                      <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <dt className="text-slate-500">Response</dt>
                          <dd className={`font-medium ${latencyClass(s.latency_ms)}`}>
                            {s.latency_ms === null ? "—" : `${s.latency_ms} ms`}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-slate-500">Uptime ({s.history.length} checks)</dt>
                          <dd className="font-medium text-slate-800">{s.uptime_pct}%</dd>
                        </div>
                        <div>
                          <dt className="text-slate-500">Last running</dt>
                          <dd className="font-medium text-slate-800">{time(s.last_up)}</dd>
                        </div>
                      </dl>
                      <div className="mt-3 flex h-5 items-end gap-0.5" aria-label="Recent checks, oldest first">
                        {s.history.map((h, i) => (
                          <span
                            key={i}
                            title={`${time(h.at)} · ${STATE_STYLE[h.state].label}${h.latency_ms !== null ? ` · ${h.latency_ms} ms` : ""}`}
                            className={`h-full w-1.5 rounded-sm ${STATE_STYLE[h.state].bar}`}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
          <p className="text-xs text-slate-500">
            Uptime and history cover checks since the UIS API last started (up to 30 per service).
          </p>
        </>
      )}
    </AppShell>
  );
}
