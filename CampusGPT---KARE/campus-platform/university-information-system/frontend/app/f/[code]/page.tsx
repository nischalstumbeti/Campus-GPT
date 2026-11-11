"use client";

import { FormEvent, useEffect, useState } from "react";
import FormFill, { FillField } from "@/components/FormFill";
import { apiFetch } from "@/lib/api";

type OpenForm = { title: string; instructions: string; fields: FillField[]; confirmation?: string; redirect_url?: string };

export default function PublicFormPage({ params }: { params: { code: string } }) {
  const [form, setForm] = useState<OpenForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [done, setDone] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<OpenForm>(`/api/v1/forms/public/${params.code}`).then(setForm).catch((e) => setErr(e.message));
  }, [params.code]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      const result = await apiFetch<{ acknowledgement: { number: string }; confirmation?: string; redirect_url?: string }>(`/api/v1/forms/public/${params.code}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers, name, email }),
      });
      setDone(`${result.confirmation || "Response recorded."} Acknowledgement ${result.acknowledgement.number}`);
      if (result.redirect_url) window.location.href = result.redirect_url;
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not submit");
    }
  };

  return (
    <main className="min-h-screen bg-slate-100 p-6">
      <form onSubmit={submit} className="mx-auto max-w-xl bg-white border rounded-lg p-5 space-y-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">CIMS form</p>
        <h1 className="text-xl font-bold text-[#0B2A4A]">{form?.title || "Form"}</h1>
        {err ? <p className="text-sm text-red-600">{err}</p> : null}
        {done ? <p className="text-sm text-emerald-700">{done}</p> : null}
        {form && !done ? (
          <>
            {form.instructions ? <p className="text-sm whitespace-pre-wrap text-slate-600">{form.instructions}</p> : null}
            <label className="block text-xs text-slate-500">Your name<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label className="block text-xs text-slate-500">Email<input type="email" className="mt-1 w-full border rounded px-2 py-1 text-sm" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
            <FormFill fields={form.fields} answers={answers} onChange={(key, value) => setAnswers({ ...answers, [key]: value })} uploadPath={`/api/v1/forms/public/${params.code}/file`} />
            <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Submit</button>
          </>
        ) : null}
      </form>
    </main>
  );
}
