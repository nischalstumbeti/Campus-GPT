"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

type Task = { id: number; title: string; notes: string; due_date: string; status: string; category: string };

function TasksInner() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [notes, setNotes] = useState("");

  const load = () => apiGet<{ tasks: Task[] }>("/api/me/tasks").then((d) => setTasks(d.tasks || [])).catch(() => setTasks([]));
  useEffect(() => { load(); }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiPost("/api/me/tasks", { title, due_date: due, notes, category: "academic" });
      setTitle(""); setDue(""); setNotes("");
      load();
    } catch {
      /* banner shows internet issue */
    }
  };

  return (
    <CopilotShell title="Campus-GPT">
    <div className="min-h-full bg-white relative">
      <main className="max-w-3xl mx-auto px-4 py-8 relative z-10">
        <h1 className="text-2xl font-bold text-primary mb-2">Task manager</h1>
        <p className="text-sm text-gray-600 mb-6">Keep academic work in one place — assignments, revision, attendance reminders.</p>
        <form onSubmit={add} className="mb-6 grid gap-2 p-4 rounded-2xl border border-gray-100 bg-white">
          <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task title" className="rounded-xl border px-3 py-2" />
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="rounded-xl border px-3 py-2" />
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes (optional)" className="rounded-xl border px-3 py-2" />
          <button className="px-4 py-2 rounded-xl bg-primary text-white font-medium w-fit">Add task</button>
        </form>
        <div className="space-y-3">
          {tasks.map((t) => (
            <div key={t.id} className="p-4 rounded-2xl border border-gray-100 bg-white flex justify-between gap-3">
              <div>
                <p className={`font-medium ${t.status === "done" ? "line-through text-gray-400" : "text-primary"}`}>{t.title}</p>
                <p className="text-xs text-gray-500">{t.due_date || "No due date"} · {t.category}</p>
                {t.notes && <p className="text-sm text-gray-600 mt-1">{t.notes}</p>}
              </div>
              <div className="flex gap-2 h-fit">
                <button
                  onClick={async () => { await apiPost(`/api/me/tasks/${t.id}/status`, { status: t.status === "done" ? "open" : "done" }); load(); }}
                  className="text-xs px-2 py-1 rounded-lg bg-primary/10 text-primary"
                >
                  {t.status === "done" ? "Reopen" : "Done"}
                </button>
                <button
                  onClick={async () => { await apiDelete(`/api/me/tasks/${t.id}`); load(); }}
                  className="text-xs px-2 py-1 rounded-lg text-red-600"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
    </CopilotShell>
  );
}

export default function TasksPage() {
  return <RequireAuth roles={["student"]}><TasksInner /></RequireAuth>;
}
