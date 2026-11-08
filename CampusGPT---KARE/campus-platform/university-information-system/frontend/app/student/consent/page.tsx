"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Item = { permission_key: string; status: string };

const LABELS: Record<string, string> = {
  "academic.attendance": "Attendance",
  "academic.marks": "Marks",
  "academic.grades": "Grades",
  "academic.cgpa": "CGPA",
  "academic.credits": "Credits / profile summary",
  "academic.courses": "Courses",
  "academic.timetable": "Timetable",
  "academic.exams": "Exams",
  "academic.history": "Academic history",
  "hostel.room": "Hostel room",
  "hostel.leave": "Hostel leave",
  "achievements.certs": "Achievements",
  "fees.records": "Fee records",
  "messaging.inbox": "Messages (admin / faculty / hostel warden)",
  "complaints.own": "My complaints",
};

export default function ConsentPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [notice, setNotice] = useState("");
  const load = useCallback(() => {
    apiFetch<{ items: Item[] }>("/api/v1/integration/campus-gpt/consents").then((d) => setItems(d.items));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (key: string, status: string) => {
    const next = status === "allow" ? "revoke" : "allow";
    await apiFetch("/api/v1/integration/campus-gpt/consents", {
      method: "PUT",
      body: JSON.stringify({ permission_key: key, status: next }),
    });
    setNotice(
      next === "revoke"
        ? `Revoked ${LABELS[key] || key}. Campus-GPT will not use this data until you allow it again.`
        : `Allowed ${LABELS[key] || key} for Campus-GPT.`
    );
    load();
  };

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-2">Campus-GPT Consent</h1>
      <p className="text-sm text-slate-600 mb-2">
        Control which UIS data Campus-GPT may request. <strong>Revoking</strong> a permission blocks that
        feature in Campus-GPT immediately (chat, pages, and actions that need it).
      </p>
      <p className="text-xs text-slate-500 mb-4">
        Example: revoke Attendance → Campus-GPT cannot answer attendance questions. General campus FAQ still works.
      </p>
      {notice && (
        <p className="text-sm mb-3 text-[#0B2A4A] bg-slate-100 border border-slate-200 rounded-lg px-3 py-2">{notice}</p>
      )}
      <ul className="bg-white border rounded-lg divide-y">
        {items.map((it) => (
          <li key={it.permission_key} className="flex items-center justify-between px-4 py-3 text-sm">
            <div>
              <p className="font-medium">{LABELS[it.permission_key] || it.permission_key}</p>
              <p className="text-xs text-slate-400">{it.permission_key}</p>
            </div>
            <button
              type="button"
              onClick={() => toggle(it.permission_key, it.status)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold border ${
                it.status === "allow"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : "bg-slate-100 text-slate-600 border-slate-200"
              }`}
            >
              {it.status === "allow" ? "Allowed · click to revoke" : "Revoked · click to allow"}
            </button>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
