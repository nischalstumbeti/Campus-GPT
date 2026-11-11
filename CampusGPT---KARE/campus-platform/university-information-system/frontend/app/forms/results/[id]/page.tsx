"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { API, apiFetch, getToken } from "@/lib/api";

type Row = { id: number; name: string; identity: string; answers: Record<string, string>; ack_number: string; created_at?: string };
type Chart = { key: string; label: string; counts: Record<string, number> };
type Field = { key: string; label: string; type: string };

const PROFILE_LABELS: Record<string, string> = {
  name: "Name",
  email: "Email",
  register_or_employee: "Register / employee no.",
  program: "Programme",
  department: "Department",
  batch: "Batch",
  section: "Section",
  semester: "Semester",
  designation: "Designation",
  school: "School",
  abc_id: "ABC ID",
};

export default function FormResultsPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [rows, setRows] = useState<Row[]>([]);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [sharePath, setSharePath] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [view, setView] = useState<"summary" | "individual">("summary");
  const [groupBy, setGroupBy] = useState("");
  const [person, setPerson] = useState(0);
  const [canEdit, setCanEdit] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    apiFetch<{ can_edit?: boolean; form: { title: string; public_code?: string; share_path?: string; fields: Field[] }; items: Row[]; charts: Chart[] }>(`/api/v1/forms/desk/${id}/responses`)
      .then((data) => {
        setTitle(data.form.title);
        setCode(data.form.public_code || "");
        setSharePath(data.form.share_path || "");
        setFields(data.form.fields || []);
        setRows(data.items || []);
        setCharts(data.charts || []);
        setCanEdit(Boolean(data.can_edit));
      })
      .catch((e) => setErr(e.message));
  }, [id]);

  const visible = rows.filter((row) => Object.entries(filters).every(([key, value]) => !value || row.answers[key] === value));
  const current = visible[person];

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

  const openPerson = (index: number) => {
    setDraft({});
    setSaved("");
    setPerson(index);
    setView("individual");
  };

  const profileLines = (row: Row) =>
    Object.entries(row.answers)
      .filter(([key]) => key.startsWith("profile:"))
      .map(([key, value]) => ({ label: PROFILE_LABELS[key.slice(8)] || key.slice(8), value }));

  const showValue = (field: Field, value: string) => {
    if (!value) return "—";
    if (field.type === "file") return "File attached";
    return value;
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">{title || "Responses"}</h1>
        <div className="p-4 space-y-4">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">{rows.length} response{rows.length === 1 ? "" : "s"}{canEdit ? " · you can correct a response" : ""}</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("csv")}>CSV</button>
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("xlsx")}>Excel</button>
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => download("pdf")}>PDF</button>
            </div>
          </div>
          {sharePath ? (
            <p className="text-sm rounded border bg-slate-50 px-3 py-2">
              Form link{" "}
              <button type="button" className="underline break-all text-left text-[#0B2A4A]" onClick={() => navigator.clipboard.writeText(`${window.location.origin}${sharePath}`)}>{`${window.location.origin}${sharePath}`}</button>
            </p>
          ) : code ? <p className="text-sm">Open link: <Link className="underline" href={`/f/${code}`}>{`${typeof window === "undefined" ? "" : window.location.origin}/f/${code}`}</Link></p> : null}
          <div className="flex gap-2">
            <button type="button" className={`px-3 py-1.5 rounded text-sm ${view === "summary" ? "bg-[#0B2A4A] text-white" : "border"}`} onClick={() => setView("summary")}>Everyone</button>
            <button type="button" className={`px-3 py-1.5 rounded text-sm ${view === "individual" ? "bg-[#0B2A4A] text-white" : "border"}`} onClick={() => setView("individual")}>One person</button>
          </div>
          {charts.length ? (
            <div className="grid md:grid-cols-2 gap-4">
              {charts.map((chart) => {
                const max = Math.max(1, ...Object.values(chart.counts));
                const total = Object.values(chart.counts).reduce((sum, count) => sum + count, 0);
                return (
                  <div key={chart.key} className="rounded-lg border bg-white p-4">
                    <p className="text-sm font-semibold text-[#0B2A4A]">{chart.label}</p>
                    <p className="text-xs text-slate-500">{total} answer{total === 1 ? "" : "s"}</p>
                    {Object.entries(chart.counts).map(([label, count]) => (
                      <div key={label} className="mt-3">
                        <div className="flex justify-between text-xs"><span>{label}</span><span>{count}</span></div>
                        <div className="mt-1 h-2 rounded bg-slate-100"><div className="h-2 rounded bg-[#0B2A4A]" style={{ width: `${(count / max) * 100}%` }} /></div>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <label className="text-xs text-slate-500">Group by question
              <select className="mt-1 block border rounded px-2 py-1 text-sm" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
                <option value="">No grouping</option>
                {fields.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
              </select>
            </label>
            {fields.filter((field) => field.type === "choice").map((field) => (
              <label key={field.key} className="text-xs text-slate-500">{field.label}
                <select className="mt-1 block border rounded px-2 py-1 text-sm" value={filters[field.key] || ""} onChange={(e) => { setFilters({ ...filters, [field.key]: e.target.value }); setPerson(0); }}>
                  <option value="">All</option>
                  {Array.from(new Set(rows.map((row) => row.answers[field.key]).filter(Boolean))).map((value) => <option key={value}>{value}</option>)}
                </select>
              </label>
            ))}
          </div>
          {view === "summary" && groupBy ? (
            <div className="space-y-3">
              {Array.from(visible.reduce((groups, row) => {
                const key = row.answers[groupBy] || "No answer";
                const list = groups.get(key) || [];
                list.push(row);
                groups.set(key, list);
                return groups;
              }, new Map<string, Row[]>())).map(([answer, people]) => (
                <div key={answer} className="rounded-lg border p-4">
                  <p className="font-medium text-[#0B2A4A]">{answer} <span className="text-slate-500 font-normal">· {people.length}</span></p>
                  <ul className="mt-2 text-sm text-slate-600">{people.map((row) => <li key={row.id}>{row.name} · {row.identity}</li>)}</ul>
                </div>
              ))}
            </div>
          ) : null}
          {view === "individual" && current ? (
            <article className="overflow-hidden rounded-lg border bg-white">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-[#0B2A4A] px-4 py-3 text-white">
                <div>
                  <p className="text-base font-semibold">{current.name}</p>
                  <p className="text-sm text-slate-200">{current.identity || "No register number"}{current.created_at ? ` · ${current.created_at.replace("T", " ").slice(0, 16)}` : ""}</p>
                </div>
                <p className="text-sm">{person + 1} of {visible.length}</p>
              </div>
              <div className="grid gap-6 p-4 md:grid-cols-[220px_1fr]">
                <div className="max-h-80 space-y-1 overflow-auto">
                  {visible.map((row, index) => (
                    <button key={row.id} type="button" className={`block w-full rounded px-2 py-2 text-left text-sm ${index === person ? "bg-[#0B2A4A] text-white" : "hover:bg-slate-50"}`} onClick={() => openPerson(index)}>
                      <span className="block font-medium">{row.name}</span>
                      <span className={`block text-xs ${index === person ? "text-slate-200" : "text-slate-500"}`}>{row.identity}</span>
                    </button>
                  ))}
                </div>
                <div className="space-y-4">
                  {profileLines(current).length ? (
                    <dl className="grid gap-2 rounded border bg-slate-50 p-3 text-sm sm:grid-cols-2">
                      {profileLines(current).map((line) => (
                        <div key={line.label}><dt className="text-xs text-slate-500">{line.label}</dt><dd className="font-medium">{line.value || "—"}</dd></div>
                      ))}
                    </dl>
                  ) : null}
                  {fields.map((field) => (
                    canEdit ? (
                      <label key={field.key} className="block text-xs text-slate-500">{field.label}
                        <input className="mt-1 w-full rounded border px-2 py-1.5 text-sm text-slate-900" value={draft[field.key] ?? current.answers[field.key] ?? ""} onChange={(e) => setDraft({ ...draft, [field.key]: e.target.value })} />
                      </label>
                    ) : (
                      <div key={field.key} className="border-b pb-2">
                        <p className="text-xs uppercase tracking-wide text-slate-500">{field.label}</p>
                        <p className="mt-1 text-sm">{showValue(field, current.answers[field.key] || "")}</p>
                      </div>
                    )
                  ))}
                  {current.ack_number ? <Link className="inline-block text-sm underline" href={`/ack/${current.ack_number}`}>Acknowledgement {current.ack_number}</Link> : <p className="text-sm text-slate-500">No acknowledgement slip for this response.</p>}
                  {saved ? <p className="text-sm text-emerald-700">{saved}</p> : null}
                  <div className="flex flex-wrap gap-2">
                    {canEdit ? <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-sm text-white" onClick={async () => {
                      const answers = { ...current.answers, ...draft };
                      await apiFetch(`/api/v1/forms/desk/${id}/responses/${current.id}`, { method: "PATCH", body: JSON.stringify({ answers }) });
                      setRows((list) => list.map((item) => item.id === current.id ? { ...item, answers } : item));
                      setDraft({});
                      setSaved("Correction saved.");
                    }}>Save correction</button> : null}
                    <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => openPerson(Math.max(0, person - 1))}>Previous</button>
                    <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => openPerson(Math.min(visible.length - 1, person + 1))}>Next</button>
                  </div>
                </div>
              </div>
            </article>
          ) : null}
          {view === "summary" ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="py-2">Person</th><th>Answers</th><th>Slip</th></tr></thead>
              <tbody>
                {visible.map((row, index) => (
                  <tr key={row.id} className="cursor-pointer border-t hover:bg-slate-50" onClick={() => openPerson(index)}>
                    <td className="py-3">
                      <span className="block font-medium text-[#0B2A4A]">{row.name}</span>
                      <span className="text-xs text-slate-500">{row.identity}</span>
                    </td>
                    <td className="py-3">{fields.map((field) => row.answers[field.key]).filter(Boolean).slice(0, 3).join(" · ") || "—"}</td>
                    <td className="py-3">{row.ack_number ? <Link className="underline" href={`/ack/${row.ack_number}`} onClick={(event) => event.stopPropagation()}>{row.ack_number}</Link> : "—"}</td>
                  </tr>
                ))}
                {!visible.length ? <tr><td colSpan={3} className="py-3 text-slate-500">No responses for this filter.</td></tr> : null}
              </tbody>
            </table>
          ) : null}
        </div>
      </section>
    </AppShell>
  );
}
