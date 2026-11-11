"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import FormFill, { FillField } from "@/components/FormFill";
import { apiFetch } from "@/lib/api";

type Item = { id: number; title: string; instructions: string; response_limit: number; used: number; remaining: number | null };
type OpenForm = Item & { fields: FillField[]; confirmation?: string; redirect_url?: string; profile?: { label: string; value: string }[]; profile_notice?: string };

function StudentForms() {
  const [items, setItems] = useState<Item[]>([]);
  const [current, setCurrent] = useState<OpenForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [slip, setSlip] = useState("");
  const [note, setNote] = useState("");
  const [redirect, setRedirect] = useState("");
  const [err, setErr] = useState("");
  const requested = useSearchParams().get("open");

  const load = () => {
    apiFetch<{ items: Item[] }>("/api/v1/forms/open")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
    if (requested) open(Number(requested)).catch(() => setErr("This form is not open for your account."));
  }, [requested]);

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
      const result = await apiFetch<{ acknowledgement: { number: string }; confirmation?: string; redirect_url?: string }>(`/api/v1/forms/open/${current.id}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setSlip(result.acknowledgement.number);
      setNote(result.confirmation || "");
      setRedirect(result.redirect_url || "");
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
          {slip ? <p className="text-sm text-emerald-700">Submitted. Acknowledgement <Link className="underline" href={`/ack/${slip}`}>{slip}</Link>{note ? ` ${note}` : ""}{redirect ? <> <a className="underline" href={redirect}>Continue</a></> : null}</p> : null}
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
              {current.profile?.length ? (
                <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
                  <p className="font-medium text-[#0B2A4A]">Taken from your account</p>
                  <p className="text-xs text-slate-600 mt-1">{current.profile_notice}</p>
                  <dl className="mt-2 space-y-1">
                    {current.profile.map((item) => (
                      <div key={item.label} className="flex justify-between gap-3"><dt>{item.label}</dt><dd className="font-medium">{item.value}</dd></div>
                    ))}
                  </dl>
                </div>
              ) : null}
              <FormFill fields={current.fields} answers={answers} onChange={(key, value) => setAnswers({ ...answers, [key]: value })} uploadPath={`/api/v1/forms/open/${current.id}/file`} />
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

export default function StudentFormsPage() {
  return (
    <Suspense fallback={<p className="p-4 text-sm text-slate-500">Loading forms…</p>}>
      <StudentForms />
    </Suspense>
  );
}
