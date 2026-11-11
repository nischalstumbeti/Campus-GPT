"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type Item = {
  id: number;
  label: string;
  href: string;
  icon: string;
  group: string;
  sort_order: number;
  visible: boolean;
};

const ROLES = ["student", "faculty", "hod", "school_dean", "admin", "university_admin", "super_admin", "director", "operator", "developer", "coe", "hostel_admin"];

export default function MenuPage() {
  const [role, setRole] = useState("student");
  const [items, setItems] = useState<Item[]>([]);
  const [form, setForm] = useState({ label: "", href: "/", icon: "file", group: "", sort_order: 0 });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = (next = role) => {
    apiFetch<{ items: Item[] }>(`/api/v1/admin/navigation?role=${next}`)
      .then((data) => setItems(data.items || []))
      .catch((e) => setErr(e.message));
  };

  useEffect(() => {
    load("student");
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      await apiFetch("/api/v1/admin/navigation", {
        method: "POST",
        body: JSON.stringify({ ...form, role, visible: true }),
      });
      setForm({ label: "", href: "/", icon: "file", group: "", sort_order: 0 });
      setMsg("Added. It appears under Added for that role. The campus menu stays.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not save");
    }
  };

  const toggle = async (item: Item) => {
    await apiFetch(`/api/v1/admin/navigation/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ visible: !item.visible }),
    });
    load();
  };

  const remove = async (item: Item) => {
    const ok = await confirmPhrase({
      title: `Delete ${item.label}`,
      detail: "This removes the menu item from the database.",
      phrase: item.label,
    });
    if (!ok) return;
    await apiFetch(`/api/v1/admin/navigation/${item.id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: item.label }),
    });
    load();
  };

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Sidebar</h1>
        <p className="px-4 py-3 text-sm text-slate-600 border-b">
          Add an extra item for one role. It is shown under Added. The campus menu stays in place. Use an address that starts with /, such as /admin/forms.
        </p>
        <div className="p-4 space-y-3">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-brand">{msg}</p> : null}
          <label className="text-xs text-slate-500">
            Role
            <select
              className="mt-1 block border rounded px-2 py-1 text-sm"
              value={role}
              onChange={(e) => {
                setRole(e.target.value);
                load(e.target.value);
              }}
            >
              {ROLES.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <form onSubmit={save} className="grid md:grid-cols-5 gap-2 items-end">
            <label className="text-xs text-slate-500">Label<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></label>
            <label className="text-xs text-slate-500 md:col-span-2">Address<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.href} onChange={(e) => setForm({ ...form, href: e.target.value })} /></label>
            <label className="text-xs text-slate-500">Group<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} /></label>
            <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Add item</button>
          </form>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-2">Label</th><th>Address</th><th>Visible</th><th></th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t">
                  <td className="py-2">{item.group ? `${item.group} · ` : ""}{item.label}</td>
                  <td>{item.href}</td>
                  <td><button type="button" className="text-xs font-semibold text-[#0B2A4A]" onClick={() => toggle(item)}>{item.visible ? "Shown" : "Hidden"}</button></td>
                  <td><button type="button" className="text-xs font-semibold text-rose-700" onClick={() => remove(item)}>Delete</button></td>
                </tr>
              ))}
              {!items.length ? <tr><td colSpan={4} className="py-3 text-slate-500">No custom items. The built-in menu is still in use.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
