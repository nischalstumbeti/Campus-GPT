"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type Field = { label: string; type: string; required: boolean; options: string };
type Service = { id: number; title: string; instructions: string; audience: string; response_limit: number; is_open: boolean };
type Answer = { id: number; name: string; identity: string; answers: Record<string, string>; ack_number: string };
type Layout = { kind: string; institution: string; document_title: string; subtitle: string; footer: string; signatory: string; signatory_title: string };

const EMPTY_FIELD: Field = { label: "", type: "text", required: true, options: "" };

export default function FormDesk({ manageLayout = false }: { manageLayout?: boolean }) {
  const [items, setItems] = useState<Service[]>([]);
  const [fields, setFields] = useState<Field[]>([{ ...EMPTY_FIELD }]);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [audience, setAudience] = useState("listed");
  const [limit, setLimit] = useState("1");
  const [selected, setSelected] = useState<number | null>(null);
  const [identities, setIdentities] = useState("");
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [layoutKind, setLayoutKind] = useState("form");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    apiFetch<{ items: Service[] }>("/api/v1/forms")
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
    if (manageLayout) {
      apiFetch<Layout>(`/api/v1/slips/layout?kind=${layoutKind}`).then(setLayout).catch(() => setLayout(null));
    }
  }, [manageLayout, layoutKind]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      const saved = await apiFetch<Service>("/api/v1/forms", {
        method: "POST",
        body: JSON.stringify({
          title,
          instructions,
          audience,
          response_limit: Number(limit),
          is_open: true,
          fields: fields.filter((field) => field.label.trim()),
        }),
      });
      setTitle("");
      setInstructions("");
      setFields([{ ...EMPTY_FIELD }]);
      setSelected(saved.id);
      setMsg("Service published. Share register numbers if only those students may fill it.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not publish the service");
    }
  };

  const openResponses = async (id: number) => {
    setSelected(id);
    setErr("");
    const data = await apiFetch<{ form: { identities: string[] }; items: Answer[] }>(`/api/v1/forms/desk/${id}/responses`);
    setIdentities((data.form.identities || []).join("\n"));
    setAnswers(data.items || []);
  };

  const share = async () => {
    if (!selected) return;
    setErr("");
    try {
      const result = await apiFetch<{ count: number }>(`/api/v1/forms/desk/${selected}/share`, {
        method: "POST",
        body: JSON.stringify({ identities }),
      });
      setMsg(`Shared with ${result.count} identities. Only a signed-in match can open it.`);
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not share");
    }
  };

  const remove = async (item: Service) => {
    const ok = await confirmPhrase({
      title: `Delete ${item.title}`,
      detail: "This removes the service, its sharing list, and the stored answers.",
      phrase: item.title,
    });
    if (!ok) return;
    await apiFetch(`/api/v1/forms/desk/${item.id}`, { method: "DELETE", body: JSON.stringify({ confirm: item.title }) });
    if (selected === item.id) setSelected(null);
    load();
  };

  const saveLayout = async (event: FormEvent) => {
    event.preventDefault();
    if (!layout) return;
    const saved = await apiFetch<Layout>("/api/v1/admin/slips/layout", { method: "PUT", body: JSON.stringify({ ...layout, kind: layoutKind }) });
    setLayout(saved);
    setMsg("Acknowledgement layout saved. The next print uses this letterhead.");
  };

  return (
    <div className="space-y-4">
      {err ? <p className="text-sm text-red-600">{err}</p> : null}
      {msg ? <p className="text-sm text-emerald-700">{msg}</p> : null}
      <section className="uis-panel">
        <h1 className="uis-panel-title">New form</h1>
        <form onSubmit={create} className="p-4 space-y-3">
          <label className="block text-xs text-slate-500">Service name
            <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="block text-xs text-slate-500">How to fill it
            <textarea className="mt-1 w-full border rounded px-2 py-1 text-sm" rows={3} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </label>
          <div className="grid md:grid-cols-2 gap-2">
            <label className="text-xs text-slate-500">Who can open it
              <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={audience} onChange={(e) => setAudience(e.target.value)}>
                <option value="listed">Only the register numbers or usernames I share</option>
                <option value="all_students">Every signed-in student</option>
                <option value="any_signed_in">Any signed-in user</option>
              </select>
            </label>
            <label className="text-xs text-slate-500">Responses allowed for one identity (0 = no limit)
              <input type="number" min={0} max={20} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={limit} onChange={(e) => setLimit(e.target.value)} />
            </label>
          </div>
          <div className="space-y-2">
            {fields.map((field, index) => (
              <div key={index} className="grid md:grid-cols-4 gap-2">
                <input className="border rounded px-2 py-1 text-sm" placeholder="Question" value={field.label} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, label: e.target.value } : item))} />
                <select className="border rounded px-2 py-1 text-sm" value={field.type} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, type: e.target.value } : item))}>
                  <option value="text">Short text</option>
                  <option value="long">Long text</option>
                  <option value="number">Number</option>
                  <option value="date">Date</option>
                  <option value="choice">Choice</option>
                </select>
                <input className="border rounded px-2 py-1 text-sm" placeholder="Choices, separated by commas" value={field.options} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, options: e.target.value } : item))} />
                <label className="text-sm flex items-center gap-2">
                  <input type="checkbox" checked={field.required} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, required: e.target.checked } : item))} />
                  Required
                </label>
              </div>
            ))}
            <button type="button" className="text-sm underline" onClick={() => setFields([...fields, { ...EMPTY_FIELD }])}>Add question</button>
          </div>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Publish form</button>
        </form>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">Published forms</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Service</th><th>Who</th><th>Limit</th><th></th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.title}</td>
                <td className="px-3 py-2">{item.audience}</td>
                <td className="px-3 py-2">{item.response_limit === 0 ? "No limit" : item.response_limit}</td>
                <td className="px-3 py-2 space-x-3">
                  <button type="button" className="text-[#0B2A4A] underline" onClick={() => openResponses(item.id)}>Share and answers</button>
                  <button type="button" className="text-rose-700" onClick={() => remove(item)}>Delete</button>
                </td>
              </tr>
            ))}
            {!items.length ? <tr><td colSpan={4} className="px-3 py-4 text-slate-500">No services yet.</td></tr> : null}
          </tbody>
        </table>
        {selected ? (
          <div className="p-4 border-t space-y-3">
            <label className="block text-xs text-slate-500">Register numbers or usernames, one on each line
              <textarea className="mt-1 w-full border rounded px-2 py-1 text-sm" rows={4} value={identities} onChange={(e) => setIdentities(e.target.value)} />
            </label>
            <p className="text-xs text-slate-500">Saving this list limits the service to these identities. A person must be signed in with that register number or username.</p>
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={share}>Save sharing list</button>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500"><tr><th className="py-2">Identity</th><th>Answers</th><th>Slip</th></tr></thead>
              <tbody>
                {answers.map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="py-2">{row.name} · {row.identity}</td>
                    <td className="py-2">{Object.values(row.answers).filter(Boolean).join(" · ")}</td>
                    <td className="py-2">{row.ack_number ? <Link className="underline" href={`/ack/${row.ack_number}`}>{row.ack_number}</Link> : "—"}</td>
                  </tr>
                ))}
                {!answers.length ? <tr><td colSpan={3} className="py-3 text-slate-500">No responses yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
      {manageLayout && layout ? (
        <section className="uis-panel">
          <h2 className="uis-panel-title">Acknowledgement layouts</h2>
          <form onSubmit={saveLayout} className="p-4 grid md:grid-cols-2 gap-2">
            <label className="text-xs text-slate-500 md:col-span-2">Which slip
              <select className="mt-1 block border rounded px-2 py-1 text-sm" value={layoutKind} onChange={(e) => setLayoutKind(e.target.value)}>
                <option value="form">Form acknowledgement</option>
                <option value="registration">Registration acknowledgement</option>
                <option value="general">Other acknowledgement</option>
              </select>
            </label>
            <label className="text-xs text-slate-500">Institution<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.institution} onChange={(e) => setLayout({ ...layout, institution: e.target.value })} /></label>
            <label className="text-xs text-slate-500">Document title<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.document_title} onChange={(e) => setLayout({ ...layout, document_title: e.target.value })} /></label>
            <label className="text-xs text-slate-500">Subtitle<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.subtitle} onChange={(e) => setLayout({ ...layout, subtitle: e.target.value })} /></label>
            <label className="text-xs text-slate-500">Signatory<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.signatory} onChange={(e) => setLayout({ ...layout, signatory: e.target.value })} /></label>
            <label className="text-xs text-slate-500">Signatory office<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.signatory_title} onChange={(e) => setLayout({ ...layout, signatory_title: e.target.value })} /></label>
            <label className="text-xs text-slate-500 md:col-span-2">Footer<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={layout.footer} onChange={(e) => setLayout({ ...layout, footer: e.target.value })} /></label>
            <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Save layout</button>
          </form>
        </section>
      ) : null}
    </div>
  );
}
