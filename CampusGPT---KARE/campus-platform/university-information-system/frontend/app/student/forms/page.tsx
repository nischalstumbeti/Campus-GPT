"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Item = { id: number; title: string; instructions: string; response_limit: number; used: number; remaining: number | null };
type Field = { key: string; label: string; type: string; required: boolean; options: string[] };
type OpenForm = Item & { fields: Field[] };

export default function StudentFormsPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [current, setCurrent] = useState<OpenForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [slip, setSlip] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    apiFetch<{ items: Item[] }>("/api/v1/forms/open")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  const open = async (id: number) => {
    setErr("");
    setSlip("");
    const form = await apiFetch<OpenForm>(`/api/v1/forms/open/${id}`);
    setCurrent(form);
    setAnswers({});
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!current) return;
    setErr("");
    try {
      const result = await apiFetch<{ acknowledgement: { number: string } }>(`/api/v1/forms/open/${current.id}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setSlip(result.acknowledgement.number);
      setCurrent(null);
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not submit");
    }
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Forms</h1>
        <div className="p-4 space-y-3">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {slip ? <p className="text-sm text-emerald-700">Submitted. Acknowledgement <Link className="underline" href={`/ack/${slip}`}>{slip}</Link></p> : null}
          {!current ? (
            <ul className="divide-y">
              {items.map((item) => (
                <li key={item.id} className="py-3 flex flex-wrap justify-between gap-2">
                  <div>
                    <p className="font-medium text-[#0B2A4A]">{item.title}</p>
                    <p className="text-xs text-slate-500">
                      {item.remaining === null ? "You can submit again" : `${item.remaining} response${item.remaining === 1 ? "" : "s"} left`}
                      {item.used ? ` · submitted ${item.used}` : ""}
                    </p>
                  </div>
                  <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => open(item.id)} disabled={item.remaining === 0}>
                    {item.remaining === 0 ? "Already submitted" : "Fill"}
                  </button>
                </li>
              ))}
              {!items.length && !err ? <li className="py-3 text-sm text-slate-500">No service is shared with your account.</li> : null}
            </ul>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              <h2 className="font-semibold text-[#0B2A4A]">{current.title}</h2>
              {current.instructions ? <p className="text-sm whitespace-pre-wrap text-slate-600">{current.instructions}</p> : null}
              {current.fields.map((field) => (
                <label key={field.key} className="block text-xs text-slate-500">
                  {field.label}{field.required ? " *" : ""}
                  {field.type === "long" ? (
                    <textarea required={field.required} className="mt-1 w-full border rounded px-2 py-1 text-sm" rows={3} value={answers[field.key] || ""} onChange={(e) => setAnswers({ ...answers, [field.key]: e.target.value })} />
                  ) : field.type === "choice" ? (
                    <select required={field.required} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={answers[field.key] || ""} onChange={(e) => setAnswers({ ...answers, [field.key]: e.target.value })}>
                      <option value="">Select</option>
                      {field.options.map((option) => <option key={option}>{option}</option>)}
                    </select>
                  ) : (
                    <input required={field.required} type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={answers[field.key] || ""} onChange={(e) => setAnswers({ ...answers, [field.key]: e.target.value })} />
                  )}
                </label>
              ))}
              <div className="flex gap-2">
                <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Submit</button>
                <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setCurrent(null)}>Back</button>
              </div>
            </form>
          )}
        </div>
      </section>
    </AppShell>
  );
}
