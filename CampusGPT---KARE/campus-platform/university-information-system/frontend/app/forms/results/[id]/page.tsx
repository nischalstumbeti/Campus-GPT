"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { API, apiFetch, getToken } from "@/lib/api";

type Row = { id: number; name: string; identity: string; answers: Record<string, string>; ack_number: string };
type Chart = { key: string; label: string; counts: Record<string, number> };
type Field = { key: string; label: string; type: string };

export default function FormResultsPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [rows, setRows] = useState<Row[]>([]);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    apiFetch<{ form: { title: string; public_code?: string; fields: Field[] }; items: Row[]; charts: Chart[] }>(`/api/v1/forms/desk/${id}/responses`)
      .then((data) => {
        setTitle(data.form.title);
        setCode(data.form.public_code || "");
        setFields(data.form.fields || []);
        setRows(data.items || []);
        setCharts(data.charts || []);
      })
      .catch((e) => setErr(e.message));
  }, [id]);

  const visible = rows.filter((row) => Object.entries(filters).every(([key, value]) => !value || row.answers[key] === value));

  const download = async (format: string) => {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API}/api/v1/forms/desk/${id}/export?format=${format}`, { headers });
    if (!res.ok) {
      setErr("Could not export");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `responses.${format === "xlsx" ? "xlsx" : format}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">{title || "Responses"}</h1>
        <div className="p-4 space-y-4">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {code ? <p className="text-sm">Open link: <Link className="underline" href={`/f/${code}`}>{`/f/${code}`}</Link></p> : null}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("csv")}>CSV</button>
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("xlsx")}>Excel</button>
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("pdf")}>PDF</button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {charts.map((chart) => {
              const max = Math.max(1, ...Object.values(chart.counts));
              return (
                <div key={chart.key} className="border rounded p-3">
                  <p className="text-sm font-medium">{chart.label}</p>
                  {Object.entries(chart.counts).map(([label, count]) => (
                    <div key={label} className="mt-2">
                      <div className="flex justify-between text-xs"><span>{label}</span><span>{count}</span></div>
                      <div className="h-2 bg-slate-100 rounded"><div className="h-2 bg-[#0B2A4A] rounded" style={{ width: `${(count / max) * 100}%` }} /></div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-2">
            {fields.filter((field) => field.type === "choice").map((field) => (
              <label key={field.key} className="text-xs text-slate-500">{field.label}
                <select className="mt-1 block border rounded px-2 py-1 text-sm" value={filters[field.key] || ""} onChange={(e) => setFilters({ ...filters, [field.key]: e.target.value })}>
                  <option value="">All</option>
                  {Array.from(new Set(rows.map((row) => row.answers[field.key]).filter(Boolean))).map((value) => <option key={value}>{value}</option>)}
                </select>
              </label>
            ))}
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500"><tr><th className="py-2">Person</th><th>Answers</th><th>Slip</th></tr></thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="py-2">{row.name} · {row.identity}</td>
                  <td className="py-2">{Object.values(row.answers).filter(Boolean).join(" · ")}</td>
                  <td className="py-2">{row.ack_number ? <Link className="underline" href={`/ack/${row.ack_number}`}>{row.ack_number}</Link> : "—"}</td>
                </tr>
              ))}
              {!visible.length ? <tr><td colSpan={3} className="py-3 text-slate-500">No responses for this filter.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
