"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Community = { id: number; name: string; purpose: string; manager: string; can_manage: boolean };
type Post = { id: number; kind: string; title: string; body: string; link_url: string; author: string; my_vote?: number; options: { id: number; label: string; votes: number }[] };
type Me = { role?: string };

export default function CommunityPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<Community[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [manager, setManager] = useState("");
  const [people, setPeople] = useState("");
  const [groupId, setGroupId] = useState("");
  const [draft, setDraft] = useState({ kind: "message", title: "", body: "", link_url: "", options: "" });
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Community[] }>("/api/v1/communities").then((data) => setItems(data.items || [])).catch((e) => setErr(e.message));
  };

  useEffect(() => {
    apiFetch<Me>("/api/v1/auth/me").then(setMe).catch(() => setMe(null));
    load();
  }, []);

  const admin = ["admin", "university_admin", "super_admin", "developer", "operator"].includes(me?.role || "");

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    try {
      await apiFetch("/api/v1/admin/communities", { method: "POST", body: JSON.stringify({ name, purpose, manager }) });
      setName("");
      setPurpose("");
      setManager("");
      setMsg("Community created. The manager can add people and post.");
      load();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not create the community");
    }
  };

  const open = async (id: number) => {
    setOpenId(id);
    setErr("");
    const data = await apiFetch<{ posts: Post[]; can_manage: boolean }>(`/api/v1/communities/${id}`);
    setPosts(data.posts || []);
    setCanManage(data.can_manage);
  };

  const addPeople = async () => {
    if (!openId) return;
    setErr("");
    try {
      const result = await apiFetch<{ added: number }>(`/api/v1/communities/${openId}/members`, {
        method: "POST",
        body: JSON.stringify({ identities: people, group_id: groupId ? Number(groupId) : null }),
      });
      setMsg(`${result.added} people added.`);
      setPeople("");
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not add people");
    }
  };

  const post = async (event: FormEvent) => {
    event.preventDefault();
    if (!openId) return;
    setErr("");
    try {
      await apiFetch(`/api/v1/communities/${openId}/posts`, { method: "POST", body: JSON.stringify(draft) });
      setDraft({ kind: "message", title: "", body: "", link_url: "", options: "" });
      open(openId);
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Could not post");
    }
  };

  const vote = async (postId: number, optionId: number) => {
    if (!openId) return;
    await apiFetch(`/api/v1/communities/${openId}/posts/${postId}/vote`, { method: "POST", body: JSON.stringify({ option_id: optionId }) });
    open(openId);
  };

  return (
    <AppShell>
      <div className="space-y-4">
        {err ? <p className="text-sm text-red-600">{err}</p> : null}
        {msg ? <p className="text-sm text-emerald-700">{msg}</p> : null}
        {admin ? (
          <section className="uis-panel">
            <h1 className="uis-panel-title">New community</h1>
            <form onSubmit={create} className="p-4 grid md:grid-cols-4 gap-2 items-end">
              <label className="text-xs text-slate-500">Name<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} /></label>
              <label className="text-xs text-slate-500">Purpose<input className="mt-1 w-full border rounded px-2 py-1 text-sm" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></label>
              <label className="text-xs text-slate-500">Manager username<input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={manager} onChange={(e) => setManager(e.target.value)} /></label>
              <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Allocate manager</button>
            </form>
          </section>
        ) : null}
        <section className="uis-panel">
          <h2 className="uis-panel-title">Your communities</h2>
          <ul className="divide-y">
            {items.map((item) => (
              <li key={item.id} className="px-4 py-3 flex justify-between gap-2">
                <div>
                  <p className="font-medium text-[#0B2A4A]">{item.name}</p>
                  <p className="text-xs text-slate-500">{item.purpose} {item.manager ? `· Manager ${item.manager}` : ""}</p>
                </div>
                <button type="button" className="text-sm underline" onClick={() => open(item.id)}>Open</button>
              </li>
            ))}
            {!items.length ? <li className="px-4 py-3 text-sm text-slate-500">You are not in a community yet.</li> : null}
          </ul>
        </section>
        {openId ? (
          <section className="uis-panel">
            <h2 className="uis-panel-title">Community board</h2>
            <div className="p-4 space-y-4">
              {canManage ? (
                <>
                  <div className="flex flex-wrap gap-2 items-end">
                    <textarea className="border rounded px-2 py-1 text-sm w-full md:w-80" rows={2} placeholder="Register numbers or usernames" value={people} onChange={(e) => setPeople(e.target.value)} />
                    <label className="text-xs text-slate-500">Or a group id
                      <input className="mt-1 block border rounded px-2 py-1 text-sm" value={groupId} onChange={(e) => setGroupId(e.target.value)} />
                    </label>
                    <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={addPeople}>Add people</button>
                  </div>
                  <form onSubmit={post} className="grid md:grid-cols-2 gap-2">
                    <select className="border rounded px-2 py-1 text-sm" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
                      <option value="message">Message</option>
                      <option value="link">Link</option>
                      <option value="document">Document link</option>
                      <option value="poll">Poll</option>
                    </select>
                    <input className="border rounded px-2 py-1 text-sm" placeholder="Title" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
                    <textarea className="border rounded px-2 py-1 text-sm md:col-span-2" rows={2} placeholder="Message" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
                    <input className="border rounded px-2 py-1 text-sm" placeholder="https:// link or document" value={draft.link_url} onChange={(e) => setDraft({ ...draft, link_url: e.target.value })} />
                    <input className="border rounded px-2 py-1 text-sm" placeholder="Poll choices, separated by commas" value={draft.options} onChange={(e) => setDraft({ ...draft, options: e.target.value })} />
                    <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Send</button>
                  </form>
                </>
              ) : null}
              {posts.map((item) => (
                <article key={item.id} className="border rounded p-3 text-sm">
                  <p className="text-xs uppercase text-slate-400">{item.kind} · {item.author}</p>
                  <h3 className="font-semibold text-[#0B2A4A]">{item.title}</h3>
                  {item.body ? <p className="mt-1 whitespace-pre-wrap">{item.body}</p> : null}
                  {item.link_url ? <a className="mt-1 inline-block underline" href={item.link_url} target="_blank" rel="noreferrer">{item.link_url}</a> : null}
                  {item.options.length ? (
                    <ul className="mt-2 space-y-1">
                      {item.options.map((option) => (
                        <li key={option.id}>
                          <button type="button" className={`underline ${item.my_vote === option.id ? "font-semibold" : ""}`} onClick={() => vote(item.id, option.id)}>
                            {option.label}
                          </button>
                          <span className="text-slate-500"> · {option.votes}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))}
              {!posts.length ? <p className="text-slate-500">Nothing has been posted.</p> : null}
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
