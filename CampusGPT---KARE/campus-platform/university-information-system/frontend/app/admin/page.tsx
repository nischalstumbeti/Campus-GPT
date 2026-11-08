"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type EmailStatus = {
  enabled: boolean;
  configured: boolean;
  smtp_host: string;
  smtp_port: number;
  from_email: string;
  from_header: string;
};

export default function AdminDashboard() {
  const [data, setData] = useState<any>(null);
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null);
  const [testTo, setTestTo] = useState("99230041300@klu.ac.in");
  const [mailTesting, setMailTesting] = useState(false);
  const [mailMsg, setMailMsg] = useState("");

  const load = () => {
    apiFetch("/api/v1/admin/dashboard").then(setData).catch(() => setData(null));
    apiFetch<EmailStatus>("/api/v1/admin/email-status")
      .then((d) => {
        setEmailStatus(d);
        if (d.from_email) setTestTo((prev) => prev || d.from_email);
      })
      .catch(() => setEmailStatus(null));
  };

  useEffect(() => {
    load();
  }, []);

  const sendTestMail = async () => {
    setMailTesting(true);
    setMailMsg("");
    try {
      const result = await apiFetch<{ ok: boolean; detail?: string; to?: string }>("/api/v1/admin/test-email", {
        method: "POST",
        body: JSON.stringify({ to: testTo || undefined }),
      });
      setMailMsg(result.ok ? `Sent to ${result.to}` : result.detail || "Send failed");
    } catch (e) {
      setMailMsg(e instanceof Error ? e.message : "Send failed");
    } finally {
      setMailTesting(false);
    }
  };

  const s = data?.stats || {};
  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-brand mb-1">{data?.welcome || "Admin"}</h1>
          <p className="text-sm text-slate-500">Institutional overview</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/admin/students/view"
            className="px-3 py-2 rounded-lg bg-brand text-white text-sm font-medium"
          >
            View students
          </Link>
          <Link
            href="/admin/students"
            className="px-3 py-2 rounded-lg border border-brand text-brand text-sm font-medium"
          >
            Filter / edit
          </Link>
          <Link
            href="/admin/users"
            className="px-3 py-2 rounded-lg border text-sm font-medium text-slate-700"
          >
            Add users / Import Excel
          </Link>
          <Link
            href="/admin/cms"
            className="px-3 py-2 rounded-lg border border-brand text-brand text-sm font-medium"
          >
            Admin CMS
          </Link>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-slate-200 bg-white px-4 py-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">Email alerts</p>
        <p className="text-lg font-semibold text-slate-800">
          {emailStatus?.configured ? "Configured" : emailStatus ? "Not configured" : "Checking…"}
        </p>
        {emailStatus?.from_email && (
          <p className="text-sm text-slate-600 mt-0.5">From: {emailStatus.from_email}</p>
        )}
        <Link href="/admin/connections" className="inline-block mt-2 text-sm font-medium text-brand">
          Change SMTP, Supabase, MongoDB, or S3
        </Link>
        <div className="mt-3 flex flex-wrap gap-2 items-center">
          <input
            type="email"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
            placeholder="Recipient email"
            className="flex-1 min-w-[220px] px-3 py-2 rounded-lg border border-slate-200 text-sm"
          />
          <button
            type="button"
            onClick={sendTestMail}
            disabled={mailTesting}
            className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-60"
          >
            {mailTesting ? "Sending…" : "Send test email"}
          </button>
        </div>
        {mailMsg && (
          <p className={`mt-2 text-sm ${mailMsg.startsWith("Sent") ? "text-emerald-700" : "text-rose-700"}`}>
            {mailMsg}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ["Students", s.students],
          ["Faculty", s.faculty],
          ["Departments", s.departments],
          ["Courses", s.courses],
        ].map(([label, value]) => (
          <div key={label as string} className="bg-white border rounded-lg p-4">
            <p className="text-xs text-slate-500 uppercase">{label}</p>
            <p className="text-2xl font-semibold text-brand mt-1">{value ?? "—"}</p>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
