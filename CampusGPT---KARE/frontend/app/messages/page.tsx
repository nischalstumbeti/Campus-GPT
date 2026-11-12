"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

type Msg = {
  id: number;
  sender_id: number;
  sender_name: string;
  body: string;
  created_at?: string;
};
type Thread = {
  id: number;
  subject: string;
  category: string;
  status: string;
  redirected_to: string;
  created_by_name: string;
  assignee_name: string;
  messages: Msg[];
  updated_at?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

function MessagesInner() {
  const { user } = useAuth();
  const role = user?.role || "student";
  const canAddress = ["faculty", "hod", "admin", "super_admin", "school_dean", "director", "operator"].includes(role);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [active, setActive] = useState<Thread | null>(null);
  const [reply, setReply] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [toRole, setToRole] = useState("admin");
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [people, setPeople] = useState<{ id: number; name: string; role: string }[]>([]);
  const [groupId, setGroupId] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const [personQuery, setPersonQuery] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<"all" | "hostel">("all");
  const wsRef = useRef<WebSocket | null>(null);

  const wardenTemplates = [
    { id: "room", label: "Room issue", subject: "Hostel room issue", body: "Hello Warden,\n\nI need help with my hostel room:\n\n" },
    { id: "leave", label: "Leave query", subject: "Hostel leave question", body: "Hello Warden,\n\nI have a question about hostel leave:\n\n" },
    { id: "mess", label: "Mess / facilities", subject: "Mess or hostel facilities", body: "Hello Warden,\n\nI would like to report a facilities issue:\n\n" },
    { id: "general", label: "Message warden", subject: "Message to Hostel Warden", body: "Hello Warden,\n\n" },
  ];

  const load = useCallback(() => {
    apiGet<{ threads: Thread[] }>("/api/messages/threads")
      .then((d) => {
        setThreads(d.threads || []);
        setActive((prev) => {
          if (!prev) return prev;
          return (d.threads || []).find((t) => t.id === prev.id) ?? null;
        });
      })
      .catch(() => setThreads([]));
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(load, 4000);
    return () => clearInterval(poll);
  }, [load]);

  useEffect(() => {
    const token = localStorage.getItem("campus_gpt_token");
    if (!token) return;
    const wsUrl = API_BASE.replace(/^http/, "ws") + `/api/messages/ws`;
    const proto =
      "cgpt." +
      btoa(token)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl, [proto]);
      wsRef.current = ws;
      ws.onopen = () => {
        try {
          ws.send(JSON.stringify({ type: "auth", token }));
        } catch {
          /* ignore */
        }
      };
      ws.onmessage = () => load();
    } catch {
      return;
    }
    return () => {
      ws.close();
    };
  }, [load]);

  useEffect(() => {
    if (!canAddress) return;
    apiGet<{ groups: { id: number; name: string }[]; users: { id: number; name: string; role: string }[] }>("/api/messages/audience")
      .then((data) => {
        setGroups(data.groups || []);
        setPeople(data.users || []);
      })
      .catch(() => {
        setGroups([]);
        setPeople([]);
      });
  }, [canAddress]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      const t = await apiPost<Thread>("/api/messages/threads", {
        subject,
        body,
        category: toRole === "hostel" ? "hostel" : "general",
        to_role: toRole,
        group_id: groupId ? Number(groupId) : null,
        user_ids: picked,
      });
      setSubject("");
      setBody("");
      setGroupId("");
      setPicked([]);
      setActive(t);
      setMsg(groupId || picked.length ? "Sent to the selected group and people." : toRole === "hostel" ? "Sent to the Hostel Warden." : "Message sent.");
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed to send");
    }
  };

  const applyWardenTemplate = (id: string) => {
    const t = wardenTemplates.find((x) => x.id === id) || wardenTemplates[3];
    setToRole("hostel");
    setSubject(t.subject);
    setBody(t.body);
    setFilter("hostel");
    setMsg("Compose ready for Hostel Warden — edit and send.");
  };

  const sendReply = async (e: FormEvent) => {
    e.preventDefault();
    if (!active || !reply.trim()) return;
    try {
      const t = await apiPost<Thread>(`/api/messages/threads/${active.id}/reply`, { body: reply });
      setReply("");
      setActive(t);
      load();
    } catch {
      setErr("Reply failed");
    }
  };

  const redirect = async (target: string) => {
    if (!active) return;
    const t = await apiPost<Thread>(`/api/messages/threads/${active.id}/redirect`, {
      redirected_to: target,
      note: `Please continue in ${target.replace("_", " ")}.`,
    });
    setActive(t);
    load();
  };

  const isStaff = role === "admin" || role === "super_admin" || role === "faculty";
  const visible = filter === "hostel" ? threads.filter((t) => t.category === "hostel") : threads;

  return (
    <CopilotShell title="Messages">
      <div className="messages-mobile-grid max-w-5xl mx-auto px-4 py-8 grid md:grid-cols-[280px_1fr] gap-4">
        <div>
          <h1 className="text-xl font-bold text-primary mb-1">Messages</h1>
          <p className="text-sm text-gray-600 mb-3">Same inbox as KARE UIS — message admin, faculty, or the hostel warden.</p>
          {err && <p className="text-xs text-red-700 mb-2">{err}</p>}
          {msg && <p className="text-xs text-emerald-700 mb-2">{msg}</p>}
          {role === "student" && (
            <div className="flex flex-wrap gap-2 mb-3">
              {wardenTemplates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => applyWardenTemplate(t.id)}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-medium border border-indigo-200 bg-indigo-50 text-indigo-900"
                >
                  {t.label}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2 mb-2">
            <button type="button" className={`text-xs px-2 py-1 rounded-lg border ${filter === "all" ? "bg-primary text-white border-primary" : "bg-white"}`} onClick={() => setFilter("all")}>All</button>
            <button type="button" className={`text-xs px-2 py-1 rounded-lg border ${filter === "hostel" ? "bg-indigo-600 text-white border-indigo-600" : "bg-white"}`} onClick={() => setFilter("hostel")}>Hostel warden</button>
          </div>
          <ul className="space-y-1 max-h-[50vh] overflow-y-auto">
            {visible.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setActive(t)}
                  className={`w-full text-left rounded-xl px-3 py-2 text-sm border ${
                    active?.id === t.id ? "border-primary bg-primary/5" : "border-gray-100 bg-white"
                  }`}
                >
                  <span className="font-medium block truncate">{t.subject}</span>
                  <span className="text-[11px] text-gray-500 capitalize">
                    {t.status}
                    {t.category === "hostel" ? " · hostel" : ""}
                    {t.redirected_to ? ` · → ${t.redirected_to}` : ""}
                  </span>
                </button>
              </li>
            ))}
            {!visible.length && (
              <li className="text-xs text-gray-500 rounded-xl border border-dashed border-gray-200 p-3">
                No threads yet. Use “Message warden” above or start an issue below.
              </li>
            )}
          </ul>

          {(role === "student" || canAddress) && (
            <form onSubmit={create} className="mt-4 space-y-2 rounded-2xl border border-gray-100 bg-white p-3">
              <p className="text-xs font-semibold text-primary">New message</p>
              <input
                required
                className="w-full border rounded-lg px-2 py-1.5 text-sm"
                placeholder="Subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
              <textarea
                required
                className="w-full border rounded-lg px-2 py-1.5 text-sm"
                rows={3}
                placeholder="Describe the issue"
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
              <select
                className="w-full border rounded-lg px-2 py-1.5 text-sm"
                value={toRole}
                onChange={(e) => setToRole(e.target.value)}
              >
                <option value="admin">Send to Admin</option>
                <option value="faculty">Send to Faculty</option>
                <option value="hostel">Send to Hostel warden</option>
              </select>
              {toRole === "hostel" && (
                <p className="text-[11px] text-indigo-700">Delivered to the hostel warden shared inbox.</p>
              )}
              {canAddress && (
                <>
                  <select className="w-full border rounded-lg px-2 py-1.5 text-sm" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                    <option value="">No group</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>{group.name}</option>
                    ))}
                  </select>
                  <input className="w-full border rounded-lg px-2 py-1.5 text-sm" placeholder="Find a person" value={personQuery} onChange={(e) => setPersonQuery(e.target.value)} />
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {people
                      .filter((person) => `${person.name} ${person.role}`.toLowerCase().includes(personQuery.toLowerCase()))
                      .slice(0, 20)
                      .map((person) => (
                        <label key={person.id} className="flex items-center gap-2 text-xs text-gray-700">
                          <input
                            type="checkbox"
                            checked={picked.includes(person.id)}
                            onChange={() => setPicked((current) => current.includes(person.id) ? current.filter((id) => id !== person.id) : [...current, person.id])}
                          />
                          <span>{person.name} · {person.role}</span>
                        </label>
                      ))}
                  </div>
                </>
              )}
              <button type="submit" className="w-full py-2 rounded-lg bg-primary text-white text-sm">
                {toRole === "hostel" ? "Send to Hostel Warden" : "Send"}
              </button>
            </form>
          )}
        </div>

        <div className="rounded-2xl border border-gray-100 bg-white p-4 min-h-[420px] flex flex-col">
          {!active ? (
            <p className="text-sm text-gray-400 m-auto">Select a thread or start a new issue.</p>
          ) : (
            <>
              <div className="border-b border-gray-100 pb-3 mb-3">
                <h2 className="font-semibold text-primary">{active.subject}</h2>
                <p className="text-xs text-gray-500">
                  From {active.created_by_name} · Assignee {active.assignee_name || "—"} · {active.status}
                  {active.redirected_to ? ` · Redirected to ${active.redirected_to}` : ""}
                </p>
                {isStaff && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    <button type="button" className="text-xs underline text-primary" onClick={() => redirect("student_login")}>
                      Redirect to student login
                    </button>
                    {(role === "admin" || role === "super_admin") && (
                      <>
                        <button type="button" className="text-xs underline text-primary" onClick={() => redirect("faculty")}>
                          Redirect to faculty
                        </button>
                        <button type="button" className="text-xs underline text-primary" onClick={() => redirect("warden")}>
                          Redirect to warden
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 mb-3">
                {active.messages.map((m) => (
                  <div key={m.id} className="rounded-xl bg-gray-50 px-3 py-2 text-sm">
                    <p className="text-[11px] text-gray-500">
                      {m.sender_name} · {m.created_at?.slice(0, 16).replace("T", " ")}
                    </p>
                    <p className="text-gray-800 whitespace-pre-wrap">{m.body}</p>
                  </div>
                ))}
              </div>
              <form onSubmit={sendReply} className="flex gap-2">
                <input
                  className="flex-1 border rounded-xl px-3 py-2 text-sm"
                  placeholder="Reply…"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <button type="submit" className="px-4 py-2 rounded-xl bg-primary text-white text-sm">
                  Reply
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </CopilotShell>
  );
}

export default function MessagesPage() {
  return (
    <RequireAuth>
      <MessagesInner />
    </RequireAuth>
  );
}
