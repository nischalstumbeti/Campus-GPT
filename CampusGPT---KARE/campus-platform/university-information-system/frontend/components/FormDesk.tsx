"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";
import { SlipDesign, SlipPaper } from "@/components/SlipPaper";

type Field = { label: string; type: string; required: boolean; options: string; show_if?: string; digits?: number };
type Service = { id: number; title: string; instructions: string; audience: string; response_limit: number; is_open: boolean };
type Answer = { id: number; name: string; identity: string; answers: Record<string, string>; ack_number: string };
type Layout = SlipDesign;

const EMPTY_FIELD: Field = { label: "", type: "text", required: true, options: "", show_if: "", digits: 0 };
const ACCOUNT_FIELDS = [
  ["name", "Name"],
  ["email", "Email"],
  ["register_or_employee", "Register number or employee id"],
  ["program", "Programme"],
  ["department", "Department"],
  ["batch", "Batch"],
  ["section", "Section"],
  ["semester", "Semester"],
  ["designation", "Designation"],
  ["school", "School"],
  ["abc_id", "ABC ID"],
] as const;

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
  const [layoutKind, setLayoutKind] = useState("general");
  const [formSlip, setFormSlip] = useState<SlipDesign | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState(false);
  const [emailMode, setEmailMode] = useState("acknowledgement");
  const [emailBody, setEmailBody] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [redirectUrl, setRedirectUrl] = useState("");
  const [collect, setCollect] = useState<string[]>(["name", "email", "register_or_employee"]);
  const [sharePath, setSharePath] = useState("");
  const [issueAck, setIssueAck] = useState(true);
  const [allowEdit, setAllowEdit] = useState(false);
  const [groups, setGroups] = useState<{ id: number; path: string }[]>([]);
  const [pickedGroup, setPickedGroup] = useState("");
  const [shareAs, setShareAs] = useState("respond");
  const [grantEdit, setGrantEdit] = useState(false);

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
    apiFetch<{ items: { id: number; path: string }[] }>("/api/v1/forms/directory").then((data) => setGroups(data.items || [])).catch(() => setGroups([]));
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
          is_open: false,
          collect: audience === "open" ? [] : collect,
          allow_edit: allowEdit,
          issue_ack: issueAck,
          fields: fields.filter((field) => field.label.trim()),
        }),
      });
      setTitle("");
      setInstructions("");
      setFields([{ ...EMPTY_FIELD }]);
      setPreview(false);
      setSelected(saved.id);
      setMsg("Draft saved. Preview it, then publish from the form below.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not publish the service");
    }
  };

  const openResponses = async (id: number) => {
    setSelected(id);
    setErr("");
    const data = await apiFetch<{ form: { identities: string[] }; items: Answer[] }>(`/api/v1/forms/desk/${id}/responses`);
    setIdentities("");
    setAnswers(data.items || []);
    const form = data.form as { email_mode?: string; email_body?: string; confirmation?: string; redirect_url?: string; slip?: Partial<SlipDesign> };
    setEmailMode(form.email_mode || "acknowledgement");
    setEmailBody(form.email_body || "");
    setConfirmation(form.confirmation || "");
    setRedirectUrl(form.redirect_url || "");
    setFormSlip({
      institution: form.slip?.institution || "Kalasalingam Academy of Research and Education",
      subtitle: form.slip?.subtitle || "University Information System",
      document_title: form.slip?.document_title || "APPLICATION CONFIRMATION",
      body: form.slip?.body || "Application number {{number}}\nStatus {{status}}\nDate {{date}}\n\n{{title}}",
      footer: form.slip?.footer || "This confirmation is for this form only.",
      signatory: form.slip?.signatory || "",
      signatory_title: form.slip?.signatory_title || "",
      show_particulars: form.slip?.show_particulars !== false,
      show_signatory: Boolean(form.slip?.show_signatory),
      page_size: form.slip?.page_size || "a4",
      orientation: form.slip?.orientation || "portrait",
      font_family: form.slip?.font_family || "Georgia",
    });
    const shared = data.form as { share_path?: string; is_open?: boolean; allow_edit?: boolean; issue_ack?: boolean };
    setSharePath(shared.is_open ? shared.share_path || "" : "");
    setAllowEdit(Boolean(shared.allow_edit));
    setIssueAck(shared.issue_ack !== false);
  };

  const share = async () => {
    if (!selected) return;
    setErr("");
    try {
      const result = await apiFetch<{ count: number }>(`/api/v1/forms/desk/${selected}/share`, {
        method: "POST",
        body: JSON.stringify({ identities, group_id: pickedGroup ? Number(pickedGroup) : null }),
      });
      setMsg(`Added ${result.count} ${result.count === 1 ? "person" : "people"}. A signed-in match can open the form.`);
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
                <option value="any_signed_in">Any signed-in CIMS user</option>
                <option value="listed">Only these signed-in identities</option>
                <option value="all_students">Every signed-in student</option>
                <option value="open">Open link, no CIMS account</option>
              </select>
            </label>
            <div className="md:col-span-2 rounded border border-slate-200 p-3">
              <p className="text-sm font-medium text-[#0B2A4A]">Account details collected with each response</p>
              <p className="mt-1 text-xs text-slate-500">Name, email, and register or employee id are selected. They are copied from the signed-in account. The person sees this list before submitting. Phone is not on the campus account, so add it as a question if you need it. An open link has no account, so these boxes do not apply there.</p>
              <div className="mt-2 flex flex-wrap gap-3">
                {ACCOUNT_FIELDS.map(([key, label]) => (
                  <label key={key} className="text-sm flex items-center gap-1">
                    <input type="checkbox" checked={collect.includes(key)} disabled={audience === "open"} onChange={(e) => setCollect(e.target.checked ? [...collect, key] : collect.filter((item) => item !== key))} />
                    {label}
                  </label>
                ))}
              </div>
            </div>
            <label className="text-sm flex items-center gap-2 md:col-span-2">
              <input type="checkbox" checked={issueAck} onChange={(e) => setIssueAck(e.target.checked)} />
              Generate an acknowledgement number and slip
            </label>
            <label className="text-sm flex items-center gap-2 md:col-span-2">
              <input type="checkbox" checked={allowEdit} onChange={(e) => setAllowEdit(e.target.checked)} />
              Let the person who filled this form edit their response
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
                  <option value="link">Link</option>
                  <option value="file">File</option>
                </select>
                <input className="border rounded px-2 py-1 text-sm" placeholder="Choices, separated by commas" value={field.options} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, options: e.target.value } : item))} />
                <input className="border rounded px-2 py-1 text-sm" placeholder="Show when f1=Yes" value={field.show_if || ""} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, show_if: e.target.value } : item))} />
                {field.type === "number" ? (
                  <select className="border rounded px-2 py-1 text-sm" value={String(field.digits || 0)} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, digits: Number(e.target.value) } : item))}>
                    <option value="0">Any count of digits</option>
                    <option value="5">Exactly 5 digits</option>
                    <option value="10">Exactly 10 digits</option>
                  </select>
                ) : null}
                <label className="text-sm flex items-center gap-2">
                  <input type="checkbox" checked={field.required} onChange={(e) => setFields(fields.map((item, i) => i === index ? { ...item, required: e.target.checked } : item))} />
                  Required
                </label>
              </div>
            ))}
            <button type="button" className="text-sm underline" onClick={() => setFields([...fields, { ...EMPTY_FIELD }])}>Add question</button>
          </div>
          <div className="flex gap-2">
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={() => setPreview((value) => !value)}>Preview</button>
            <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Save draft</button>
          </div>
          {preview ? (
            <div className="border rounded p-3 bg-slate-50">
              <p className="text-xs text-slate-500 mb-2">Preview only. Nothing is stored.</p>
              <p className="font-medium">{title || "Untitled form"}</p>
              <p className="text-sm whitespace-pre-wrap text-slate-600">{instructions}</p>
              <ul className="mt-2 text-sm list-disc pl-4">
                {fields.filter((field) => field.label.trim()).map((field) => <li key={field.label}>{field.label} · {field.type}{field.show_if ? ` · shown when ${field.show_if}` : ""}</li>)}
              </ul>
            </div>
          ) : null}
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
            <div className="grid md:grid-cols-2 gap-2">
              <label className="text-xs text-slate-500">Add from a group, including its subgroups
                <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={pickedGroup} onChange={(e) => setPickedGroup(e.target.value)}>
                  <option value="">Choose a group</option>
                  {groups.map((group) => <option key={group.id} value={group.id}>{group.path}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-500">Or one person
                <input className="mt-1 w-full border rounded px-2 py-1 text-sm" placeholder="Register number or username" value={identities} onChange={(e) => setIdentities(e.target.value)} />
              </label>
              <label className="text-xs text-slate-500">Add them as
                <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={shareAs} onChange={(e) => setShareAs(e.target.value)}>
                  <option value="respond">People who can fill the form</option>
                  <option value="collaborate">Collaborators who can view responses</option>
                </select>
              </label>
              {shareAs === "collaborate" ? (
                <label className="text-sm flex items-center gap-2">
                  <input type="checkbox" checked={grantEdit} onChange={(e) => setGrantEdit(e.target.checked)} />
                  They may edit a response
                </label>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={async () => {
                const body = { identities, group_id: pickedGroup ? Number(pickedGroup) : null, can_edit: grantEdit };
                if (shareAs === "collaborate") {
                  const result = await apiFetch<{ added: number }>(`/api/v1/forms/desk/${selected}/collaborators`, { method: "POST", body: JSON.stringify(body) });
                  setMsg(`${result.added} collaborator${result.added === 1 ? "" : "s"} added${grantEdit ? ", with permission to edit responses" : ""}.`);
                } else {
                  await share();
                }
              }}>Add</button>
              <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={async () => {
                await apiFetch(`/api/v1/forms/desk/${selected}`, { method: "PATCH", body: JSON.stringify({ is_open: true, audience, collect: audience === "open" ? [] : collect, allow_edit: allowEdit, issue_ack: issueAck }) });
                setMsg("Published. Copy the link below and share it.");
                load();
                if (selected) openResponses(selected);
              }}>Publish</button>
              <Link className="px-3 py-1.5 rounded border text-sm" href={`/forms/results/${selected}`}>Charts and export</Link>
            </div>
            {sharePath ? (
              <p className="text-sm">
                Share link{" "}
                <button type="button" className="underline text-[#0B2A4A] break-all text-left" onClick={() => navigator.clipboard.writeText(`${window.location.origin}${sharePath}`)}>
                  {`${window.location.origin}${sharePath}`}
                </button>
              </p>
            ) : null}
            <div className="grid md:grid-cols-2 gap-2">
              <label className="text-xs text-slate-500">After submit, email
                <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={emailMode} onChange={(e) => setEmailMode(e.target.value)}>
                  <option value="acknowledgement">Acknowledgement slip</option>
                  <option value="message">A normal message</option>
                  <option value="none">Do not email</option>
                </select>
              </label>
              <label className="text-xs text-slate-500">Message text<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={emailBody} onChange={(e) => setEmailBody(e.target.value)} /></label>
              <label className="text-xs text-slate-500">On-screen confirmation<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label>
              <label className="text-xs text-slate-500">Destination link<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={redirectUrl} onChange={(e) => setRedirectUrl(e.target.value)} /></label>
              <p className="text-xs text-slate-500 md:col-span-2">Edit this form’s slip on the page below. The printed acknowledgement uses that page.</p>
            </div>
            {formSlip ? <SlipPaper editing design={formSlip} onChange={setFormSlip} lines={[{ label: "Sample answer", value: "Shown where particulars are turned on" }]} /> : null}
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={async () => {
              await apiFetch(`/api/v1/forms/desk/${selected}`, { method: "PATCH", body: JSON.stringify({ email_mode: emailMode, email_body: emailBody, confirmation, redirect_url: redirectUrl, slip: formSlip }) });
              setMsg("This form’s slip and email were saved.");
            }}>Save slip and email</button>
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
        <section id="slip-design" className="uis-panel">
          <h2 className="uis-panel-title">Slip design</h2>
          <p className="px-4 pt-3 text-sm text-slate-600">Choose the service, then edit the page the way it will print. Tokens such as {"{{number}}"} are filled when the slip is issued. A form can also keep its own page from the form above.</p>
          <div className="p-4 space-y-3">
            <label className="text-xs text-slate-500">Which slip
              <select className="mt-1 block border rounded px-2 py-1 text-sm" value={layoutKind} onChange={(e) => setLayoutKind(e.target.value)}>
                {["general", "form", "registration", "withdrawal", "revaluation", "arrear", "backlog", "makeup", "payment", "complaint"].map((kind) => <option key={kind} value={kind}>{kind}</option>)}
              </select>
            </label>
            <SlipPaper editing design={{ ...layout, kind: layoutKind }} onChange={(next) => setLayout(next)} lines={[{ label: "Particular", value: "Filled from the record" }]} />
            <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => saveLayout({ preventDefault() {} } as FormEvent)}>Save this slip</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
