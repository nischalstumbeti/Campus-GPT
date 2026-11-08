"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiDownload, apiFetch, getToken } from "@/lib/api";

type Attachment = { id: number; filename: string; size: number };
type Msg = {
  id: number;
  sender_id: number;
  sender_name: string;
  body: string;
  created_at?: string;
  attachments?: Attachment[];
};
type Thread = {
  id: number;
  subject: string;
  category?: string;
  status: string;
  redirected_to: string;
  created_by_name: string;
  assignee_name: string;
  messages: Msg[];
};

const WARDEN_TEMPLATES = [
  {
    id: "room",
    label: "Room issue",
    subject: "Hostel room issue",
    body: "Hello Warden,\n\nI need help with my hostel room (repair / roommate / facilities):\n\n",
  },
  {
    id: "leave",
    label: "Leave query",
    subject: "Hostel leave question",
    body: "Hello Warden,\n\nI have a question about my hostel leave / outing permission:\n\n",
  },
  {
    id: "mess",
    label: "Mess / facilities",
    subject: "Mess or hostel facilities",
    body: "Hello Warden,\n\nI would like to report a mess / water / electricity / facilities issue:\n\n",
  },
  {
    id: "general",
    label: "Message warden",
    subject: "Message to Hostel Warden",
    body: "Hello Warden,\n\n",
  },
];

export default function MessagesPage() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [active, setActive] = useState<Thread | null>(null);
  const [role, setRole] = useState("student");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [toRole, setToRole] = useState("admin");
  const [reply, setReply] = useState("");
  const [composeFiles, setComposeFiles] = useState<File[]>([]);
  const [replyFiles, setReplyFiles] = useState<File[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<"all" | "hostel">("all");

  const load = useCallback(() => {
    apiFetch<{ threads: Thread[] }>("/api/v1/messages/threads")
      .then((d) => {
        setThreads(d.threads || []);
        setActive((prev) => (prev ? (d.threads || []).find((t) => t.id === prev.id) ?? null : prev));
      })
      .catch(() => setThreads([]));
  }, []);

  useEffect(() => {
    apiFetch<{ role: string }>("/api/v1/auth/me").then((m) => setRole(m.role)).catch(() => null);
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    setMsg("");
    try {
      const facultySender = role === "faculty" || role === "hod" || role === "school_dean";
      let t: Thread;
      if (facultySender) {
        const form = new FormData();
        form.append("subject", subject);
        form.append("body", body);
        form.append("to_role", toRole);
        composeFiles.forEach((file) => form.append("files", file));
        t = await apiFetch<Thread>("/api/v1/messages/threads/with-files", { method: "POST", body: form });
      } else {
        t = await apiFetch<Thread>("/api/v1/messages/threads", {
          method: "POST",
          body: JSON.stringify({
            subject,
            body,
            category: toRole === "hostel" ? "hostel" : "general",
            to_role: toRole,
          }),
        });
      }
      setSubject("");
      setBody("");
      setComposeFiles([]);
      setActive(t);
      setMsg(
        toRole === "hostel"
          ? "Sent to the Hostel Warden. They will see it in the hostel inbox."
          : "Message sent (synced with Campus-GPT via UIS)."
      );
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Failed");
    }
  };

  const applyWardenTemplate = (id: string) => {
    const t = WARDEN_TEMPLATES.find((x) => x.id === id) || WARDEN_TEMPLATES[3];
    setToRole("hostel");
    setSubject(t.subject);
    setBody(t.body);
    setFilter("hostel");
    setMsg("Compose ready for Hostel Warden — edit and send.");
  };

  const sendReply = async (e: FormEvent) => {
    e.preventDefault();
    if (!active) return;
    try {
      const facultySender = role === "faculty" || role === "hod" || role === "school_dean";
      let t: Thread;
      if (facultySender) {
        const form = new FormData();
        form.append("body", reply);
        replyFiles.forEach((file) => form.append("files", file));
        t = await apiFetch<Thread>(`/api/v1/messages/threads/${active.id}/reply-with-files`, {
          method: "POST",
          body: form,
        });
      } else {
        t = await apiFetch<Thread>(`/api/v1/messages/threads/${active.id}/reply`, {
          method: "POST",
          body: JSON.stringify({ body: reply }),
        });
      }
      setReply("");
      setReplyFiles([]);
      setActive(t);
      load();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Reply failed");
    }
  };

  const downloadAttachment = (file: Attachment) => {
    if (!getToken()) return;
    apiDownload(`/api/v1/messages/attachments/${file.id}`, file.filename).catch(() => setErr("Could not download the file"));
  };

  const isStaff = ["faculty", "hod", "admin", "university_admin", "super_admin", "hostel_admin"].includes(role);
  const canCompose = role === "student" || role === "faculty" || role === "hod";
  const visible = filter === "hostel" ? threads.filter((t) => t.category === "hostel") : threads;

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand mb-1">Messages</h1>
      <p className="text-sm text-slate-600 mb-4">
        Same inbox as Campus-GPT — message admin, faculty, or the hostel warden.
        {(role === "faculty" || role === "hod" || role === "school_dean") && " Faculty can attach files to a new message or a reply."}
      </p>
      {err && <p className="text-sm text-red-700 mb-2">{err}</p>}
      {msg && <p className="text-sm text-emerald-700 mb-2">{msg}</p>}

      {role === "student" && (
        <div className="mb-4 flex flex-wrap gap-2">
          {WARDEN_TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => applyWardenTemplate(t.id)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-indigo-200 bg-indigo-50 text-indigo-900"
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className="grid md:grid-cols-[260px_1fr] gap-4">
        <div>
          <div className="flex gap-2 mb-2">
            <button
              type="button"
              className={`text-xs px-2 py-1 rounded border ${filter === "all" ? "bg-brand text-white border-brand" : "bg-white"}`}
              onClick={() => setFilter("all")}
            >
              All
            </button>
            <button
              type="button"
              className={`text-xs px-2 py-1 rounded border ${filter === "hostel" ? "bg-indigo-600 text-white border-indigo-600" : "bg-white"}`}
              onClick={() => setFilter("hostel")}
            >
              Hostel warden
            </button>
          </div>
          <ul className="space-y-1 max-h-[50vh] overflow-y-auto">
            {visible.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setActive(t)}
                  className={`w-full text-left rounded-md px-3 py-2 text-sm border ${
                    active?.id === t.id ? "border-brand bg-brand/5" : "border-slate-200 bg-white"
                  }`}
                >
                  <span className="font-medium block truncate">{t.subject}</span>
                  <span className="text-[11px] text-slate-500 capitalize">
                    {t.status}
                    {t.category === "hostel" ? " · hostel" : ""}
                  </span>
                </button>
              </li>
            ))}
            {!visible.length && (
              <li className="text-xs text-slate-400 border border-dashed rounded-md p-3">No threads in this view.</li>
            )}
          </ul>
          {canCompose && (
            <form onSubmit={create} className="mt-3 space-y-2 bg-white border border-slate-200 rounded-lg p-3">
              <p className="text-xs font-semibold text-brand">New message</p>
              <input
                className="w-full border rounded-md px-2 py-1.5 text-sm"
                placeholder="Subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              />
              <textarea
                className="w-full border rounded-md px-2 py-1.5 text-sm"
                rows={3}
                placeholder="Describe the issue"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                required
              />
              <select
                className="w-full border rounded-md px-2 py-1.5 text-sm"
                value={toRole}
                onChange={(e) => setToRole(e.target.value)}
              >
                <option value="admin">Admin</option>
                <option value="faculty">Faculty</option>
                <option value="hostel">Hostel warden</option>
              </select>
              {toRole === "hostel" && (
                <p className="text-[11px] text-indigo-700">This goes to the hostel warden inbox for approval / hostel help.</p>
              )}
              {(role === "faculty" || role === "hod" || role === "school_dean") && (
                <label className="block text-[11px] text-slate-600">
                  Attachments
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.png,.jpg,.jpeg,.csv,.xlsx"
                    className="mt-1 block w-full text-xs"
                    onChange={(e) => setComposeFiles(Array.from(e.target.files || []))}
                  />
                  {composeFiles.length > 0 && (
                    <span className="block mt-1 text-slate-500">{composeFiles.map((f) => f.name).join(", ")}</span>
                  )}
                </label>
              )}
              <button type="submit" className="w-full py-2 bg-brand text-white rounded-md text-sm">
                {toRole === "hostel" ? "Send to Hostel Warden" : "Send"}
              </button>
            </form>
          )}
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4 min-h-[360px] flex flex-col">
          {!active ? (
            <p className="text-sm text-slate-400 m-auto">Select a thread or message the hostel warden above.</p>
          ) : (
            <>
              <h2 className="font-semibold text-brand">{active.subject}</h2>
              <p className="text-xs text-slate-500 mb-3">
                From {active.created_by_name} · Assignee {active.assignee_name || "—"}
                {active.category === "hostel" ? " · Hostel" : ""}
              </p>
              <div className="flex-1 overflow-y-auto space-y-2 mb-3">
                {active.messages.map((m) => (
                  <div key={m.id} className="rounded-md bg-slate-50 px-3 py-2 text-sm">
                    <p className="text-[11px] text-slate-500">{m.sender_name}</p>
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    {!!m.attachments?.length && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {m.attachments.map((file) => (
                          <button
                            key={file.id}
                            type="button"
                            onClick={() => downloadAttachment(file)}
                            className="text-xs px-2 py-1 rounded border border-slate-300 bg-white text-brand"
                          >
                            {file.filename}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <form onSubmit={sendReply} className="space-y-2">
                <div className="flex gap-2">
                  <input
                    className="flex-1 border rounded-md px-3 py-2 text-sm"
                    placeholder="Reply…"
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                  />
                  <button type="submit" className="px-4 py-2 bg-brand text-white rounded-md text-sm">
                    Reply
                  </button>
                </div>
                {(role === "faculty" || role === "hod" || role === "school_dean") && (
                  <label className="block text-[11px] text-slate-600">
                    Attach files
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.png,.jpg,.jpeg,.csv,.xlsx"
                      className="mt-1 block w-full text-xs"
                      onChange={(e) => setReplyFiles(Array.from(e.target.files || []))}
                    />
                    {replyFiles.length > 0 && (
                      <span className="block mt-1 text-slate-500">{replyFiles.map((f) => f.name).join(", ")}</span>
                    )}
                  </label>
                )}
              </form>
              {isStaff && (
                <button
                  type="button"
                  className="mt-2 text-xs text-brand underline self-start"
                  onClick={async () => {
                    setErr("");
                    try {
                      const t = await apiFetch<Thread>(`/api/v1/messages/threads/${active.id}/redirect`, {
                        method: "POST",
                        body: JSON.stringify({
                          redirected_to: "student_login",
                          note: "Please continue from student login.",
                        }),
                      });
                      setActive(t);
                      setMsg("Redirected to student login.");
                      load();
                    } catch (ex) {
                      setErr(ex instanceof Error ? ex.message : "Redirect failed");
                    }
                  }}
                >
                  Redirect to student login
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
