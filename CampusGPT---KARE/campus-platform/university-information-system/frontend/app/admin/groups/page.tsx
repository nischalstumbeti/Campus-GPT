"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type Group = { id: number; name: string; parent_id: number | null; purpose: string; members: { user_id: number; label: string }[] };

export default function GroupsPage() {
  const [items, setItems] = useState<Group[]>([]);
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [purpose, setPurpose] = useState("");
  const [identities, setIdentities] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => {
    apiFetch<{ items: Group[] }>("/api/v1/admin/groups").then((data) => setItems(data.items || [])).catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load();
  }, []);

  const visible = items.filter((group) => !group.purpose.startsWith("office-route:"));

  const path = (group: Group): string => {
    const parentRow = items.find((item) => item.id === group.parent_id);
    return parentRow ? `${path(parentRow)} / ${group.name}` : group.name;
  };

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    await apiFetch("/api/v1/admin/groups", {
      method: "POST",
      body: JSON.stringify({ name, purpose, parent_id: parent ? Number(parent) : null }),
    });
    setName("");
    setPurpose("");
    setMsg("Group saved. Add people by register number or username.");
    load();
  };

  const add = async (group: Group) => {
    setErr("");
    try {
      const result = await apiFetch<{ added: number }>(`/api/v1/admin/groups/${group.id}/members`, {
        method: "POST",
        body: JSON.stringify({ identities: identities[group.id] || "" }),
      });
      setMsg(`${result.added} people added to ${path(group)}.`);
      setIdentities({ ...identities, [group.id]: "" });
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not add people");
    }
  };

  const remove = async (group: Group) => {
    const ok = await confirmPhrase({ title: `Delete ${group.name}`, detail: "People stay in the system. This only removes the label.", phrase: group.name });
    if (!ok) return;
    await apiFetch(`/api/v1/admin/groups/${group.id}`, { method: "DELETE", body: JSON.stringify({ confirm: group.name }) });
    load();
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Groups</h1>
        <form onSubmit={create} className="p-4 grid md:grid-cols-4 gap-2 items-end">
          {err ? <p className="md:col-span-4 text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="md:col-span-4 text-sm text-emerald-700">{msg}</p> : null}
          <label className="text-xs text-slate-500">Name<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="text-xs text-slate-500">Inside
            <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={parent} onChange={(e) => setParent(e.target.value)}>
              <option value="">No parent</option>
              {visible.map((item) => <option key={item.id} value={item.id}>{path(item)}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-500">Why this label<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Add group</button>
        </form>
      </section>
      <div className="space-y-3">
        {visible.map((group) => (
          <section key={group.id} className="uis-panel">
            <h2 className="uis-panel-title">{path(group)}</h2>
            <div className="p-4 space-y-2">
              {group.purpose ? <p className="text-sm text-slate-600">{group.purpose}</p> : null}
              <ul className="text-sm">
                {group.members.map((member) => <li key={member.user_id}>{member.label}</li>)}
                {!group.members.length ? <li className="text-slate-500">No one in this label yet.</li> : null}
              </ul>
              <div className="flex flex-wrap gap-2 items-end">
                <textarea className="border rounded px-2 py-1 text-sm w-full md:w-96" rows={2} placeholder="Register numbers or usernames" value={identities[group.id] || ""} onChange={(e) => setIdentities({ ...identities, [group.id]: e.target.value })} />
                <button type="button" className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm" onClick={() => add(group)}>Add people</button>
                <button type="button" className="px-3 py-1.5 rounded border text-sm text-rose-700" onClick={() => remove(group)}>Delete group</button>
              </div>
            </div>
          </section>
        ))}
      </div>
    </AppShell>
  );
}
