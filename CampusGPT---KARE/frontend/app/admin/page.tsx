"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { BarChart3, BrainCircuit, FileUp, FolderOpen, Loader2 } from "lucide-react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet, apiPost, apiPostForm } from "@/lib/api";

type AnalyticsSummary = {
  total_queries: number;
  failed_count: number;
  top_queries: { query: string; count: number }[];
};

type EmailStatus = {
  enabled: boolean;
  configured: boolean;
  smtp_host: string;
  smtp_port: number;
  from_email: string;
  from_header: string;
};

type DirectoryUser = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  uis_username: string;
};

const MAIL_ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.csv,.xlsx,.png,.jpg,.jpeg";

function AdminInner() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [chunks, setChunks] = useState<number | null>(null);
  const [emailStatus, setEmailStatus] = useState<EmailStatus | null>(null);
  const [userQuery, setUserQuery] = useState("");
  const [userResults, setUserResults] = useState<DirectoryUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<DirectoryUser | null>(null);
  const [testTo, setTestTo] = useState("");
  const [mailSubject, setMailSubject] = useState("Campus-GPT notice");
  const [mailDescription, setMailDescription] = useState(
    "This is a notice from Campus-GPT admin."
  );
  const [mailFiles, setMailFiles] = useState<File[]>([]);
  const [mailTesting, setMailTesting] = useState(false);
  const [mailMsg, setMailMsg] = useState("");
  const [training, setTraining] = useState(false);
  const [trainMsg, setTrainMsg] = useState("");
  const [statsError, setStatsError] = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadStats = () => {
    setStatsError(null);
    apiGet<AnalyticsSummary>("/api/analytics/public")
      .then((d) =>
        setAnalytics({
          total_queries: Number(d.total_queries) || 0,
          failed_count: Number(d.failed_count) || 0,
          top_queries: Array.isArray(d.top_queries) ? d.top_queries : [],
        })
      )
      .catch((e: Error) => {
        setStatsError(e.message || "Could not load analytics");
        setAnalytics({ total_queries: 0, failed_count: 0, top_queries: [] });
      });
    apiGet<{ total_chunks: number }>("/api/admin/vector-stats/public")
      .then((d) => setChunks(d.total_chunks ?? 0))
      .catch(() => setChunks(null));
    apiGet<EmailStatus>("/api/admin/email-status")
      .then((d) => {
        setEmailStatus(d);
      })
      .catch(() => setEmailStatus(null));
  };

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      const q = userQuery.trim();
      apiGet<{ users: DirectoryUser[] }>(
        `/api/admin/users?limit=25${q ? `&q=${encodeURIComponent(q)}` : "&role=student"}`
      )
        .then((d) => setUserResults(Array.isArray(d.users) ? d.users : []))
        .catch(() => setUserResults([]));
    }, 280);
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [userQuery]);

  const sendTestMail = async () => {
    const recipient = (selectedUser?.email || testTo || "").trim();
    if (!recipient) {
      setMailMsg("Select a user or enter a recipient email");
      return;
    }
    setMailTesting(true);
    setMailMsg("");
    try {
      const form = new FormData();
      form.append("to", recipient);
      if (selectedUser?.id) form.append("user_id", String(selectedUser.id));
      form.append("subject", mailSubject.trim() || "Campus-GPT notice");
      form.append("description", mailDescription.trim() || "Message from Campus-GPT admin.");
      mailFiles.forEach((f) => form.append("files", f));
      const data = await apiPostForm<{
        ok: boolean;
        detail?: string;
        to?: string;
        attachments?: string[];
      }>("/api/admin/send-mail", form);
      const att =
        data.attachments && data.attachments.length
          ? ` · ${data.attachments.length} attachment(s)`
          : "";
      setMailMsg(data.ok ? `Sent to ${data.to}${att}` : data.detail || "Send failed");
    } catch (e) {
      setMailMsg(e instanceof Error ? e.message : "Send failed");
    } finally {
      setMailTesting(false);
    }
  };

  const trainModel = async () => {
    setTraining(true);
    setTrainMsg("");
    try {
      const data = await apiPost<{
        message?: string;
        chunks_indexed?: number;
        seed_chunks?: number;
        uis_chunks?: number;
        detail?: string;
      }>("/api/admin/train/public", {});
      setTrainMsg(
        data.message ||
          `Trained successfully · ${data.chunks_indexed ?? 0} chunks (seed ${data.seed_chunks ?? 0}, UIS ${data.uis_chunks ?? 0}).`
      );
      setChunks(data.chunks_indexed ?? chunks);
      loadStats();
    } catch (e) {
      setTrainMsg(e instanceof Error ? e.message : "Training failed");
    } finally {
      setTraining(false);
    }
  };

  return (
    <CopilotShell title="Admin">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-primary">Admin Dashboard</h1>
          <p className="text-sm text-gray-600 mt-1">Knowledge, training, analytics, and campus notices.</p>
        </div>

        <div className="mb-6 rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Email / notices</p>
              <p className="text-lg font-semibold text-slate-800">
                {emailStatus?.configured ? "Configured" : emailStatus ? "Not configured" : "Checking…"}
              </p>
              {emailStatus?.from_email && (
                <p className="text-sm text-slate-600 mt-0.5">
                  From: {emailStatus.from_email}
                  {emailStatus.smtp_host ? ` · ${emailStatus.smtp_host}:${emailStatus.smtp_port}` : ""}
                </p>
              )}
            </div>
            <Link href="/admin/connections" className="text-sm font-medium text-primary">
              Change SMTP or data store
            </Link>
          </div>

          <div className="mt-4 grid gap-3">
            <div>
              <label className="text-xs font-medium text-slate-600">Find particular user</label>
              <input
                type="search"
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                placeholder="Search name, email, or UIS username"
                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
              />
              {userResults.length > 0 && (
                <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-slate-100 divide-y">
                  {userResults.map((u) => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => {
                        setSelectedUser(u);
                        setTestTo(u.email);
                        setUserResults([]);
                        setUserQuery(u.full_name || u.email);
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${
                        selectedUser?.id === u.id ? "bg-primary/5" : ""
                      }`}
                    >
                      <span className="font-medium text-slate-800">{u.full_name || "—"}</span>
                      <span className="text-slate-500"> · {u.email}</span>
                      <span className="text-xs text-slate-400"> · {u.role}</span>
                    </button>
                  ))}
                </div>
              )}
              {selectedUser && (
                <p className="mt-1 text-xs text-emerald-700">
                  Selected: {selectedUser.full_name || selectedUser.email} ({selectedUser.email})
                </p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-600">Or type email manually</label>
              <input
                type="email"
                value={testTo}
                onChange={(e) => {
                  setTestTo(e.target.value);
                  setSelectedUser(null);
                }}
                placeholder="student@klu.ac.in"
                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-600">Subject</label>
              <input
                type="text"
                value={mailSubject}
                onChange={(e) => setMailSubject(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-600">Description / message</label>
              <textarea
                value={mailDescription}
                onChange={(e) => setMailDescription(e.target.value)}
                rows={4}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm resize-y"
                placeholder="Write the notice body shown in the email…"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-600">
                Attach PDF / documents (optional, max 5 × 8 MB)
              </label>
              <input
                type="file"
                accept={MAIL_ACCEPT}
                multiple
                onChange={(e) => setMailFiles(Array.from(e.target.files || []).slice(0, 5))}
                className="mt-1 block w-full text-sm text-slate-600"
              />
              {mailFiles.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">
                  {mailFiles.map((f) => f.name).join(", ")}
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={sendTestMail}
                disabled={mailTesting || !emailStatus?.configured}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-60"
              >
                {mailTesting ? "Sending…" : "Send email to user"}
              </button>
            </div>
          </div>

          {mailMsg && (
            <p className={`mt-2 text-sm ${mailMsg.startsWith("Sent") ? "text-emerald-700" : "text-rose-700"}`}>
              {mailMsg}
            </p>
          )}
          {!emailStatus?.configured && emailStatus && (
            <p className="mt-2 text-sm text-amber-700">
              SMTP is not configured. Set EMAIL_ENABLED, SMTP_USER, and SMTP_PASSWORD in backend/.env, then restart the API.
            </p>
          )}
        </div>

        <div className="grid md:grid-cols-3 gap-4 mb-8">
          <Link
            href="/admin/upload"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <FileUp className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Upload Center</h3>
              <p className="text-gray-600 text-sm">Add policies and PDFs to the knowledge base</p>
            </div>
          </Link>

          <button
            type="button"
            onClick={trainModel}
            disabled={training}
            className="text-left p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4 disabled:opacity-70"
          >
            <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center">
              {training ? (
                <Loader2 className="w-6 h-6 text-emerald-700 animate-spin" />
              ) : (
                <BrainCircuit className="w-6 h-6 text-emerald-700" />
              )}
            </div>
            <div>
              <h3 className="font-semibold text-primary">Train the model</h3>
              <p className="text-gray-600 text-sm">Rebuild answers from KARE + live UIS data</p>
              {chunks != null && (
                <p className="text-xs text-gray-500 mt-1">Knowledge chunks: {chunks}</p>
              )}
            </div>
          </button>

          <Link
            href="/admin/evaluation"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-violet-50 flex items-center justify-center">
              <BarChart3 className="w-6 h-6 text-violet-700" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Evaluation</h3>
              <p className="text-gray-600 text-sm">Latency + gold-suite accuracy proxies</p>
            </div>
          </Link>

          <Link
            href="/admin/analytics"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-secondary/10 flex items-center justify-center">
              <BarChart3 className="w-6 h-6 text-secondary" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Analytics</h3>
              <p className="text-gray-600 text-sm">Usage insights, trends, and student points</p>
            </div>
          </Link>

          <Link
            href="/admin/cms"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center">
              <FileUp className="w-6 h-6 text-amber-700" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Admin CMS</h3>
              <p className="text-gray-600 text-sm">Branding, colors, fonts, backgrounds, marquee</p>
            </div>
          </Link>

          <Link
            href="/admin/announcements"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center">
              <FileUp className="w-6 h-6 text-amber-700" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Announcements</h3>
              <p className="text-gray-600 text-sm">Publish notices to students, faculty, and warden</p>
            </div>
          </Link>

          <Link
            href="/messages"
            className="p-5 rounded-2xl bg-white border border-gray-100 hover:border-primary/20 transition-all flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-xl bg-sky-50 flex items-center justify-center">
              <FolderOpen className="w-6 h-6 text-sky-700" />
            </div>
            <div>
              <h3 className="font-semibold text-primary">Inbox</h3>
              <p className="text-gray-600 text-sm">Reply to student and faculty messages</p>
            </div>
          </Link>
        </div>

        {trainMsg && (
          <div className="mb-6 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {trainMsg}
          </div>
        )}
        {statsError && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {statsError}
          </div>
        )}

        <div className="rounded-2xl bg-white border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-primary" />
            <h2 className="font-semibold text-primary">Analytics Summary</h2>
          </div>
          <div className="p-5">
            {analytics ? (
              <div className="grid md:grid-cols-3 gap-6">
                <div>
                  <p className="text-sm text-gray-500">Total Queries</p>
                  <p className="text-2xl font-bold text-primary">{analytics.total_queries}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Failed / Escalated</p>
                  <p className="text-2xl font-bold text-amber-600">{analytics.failed_count}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Failure Rate</p>
                  <p className="text-2xl font-bold text-secondary">
                    {analytics.total_queries
                      ? ((analytics.failed_count / analytics.total_queries) * 100).toFixed(1)
                      : "0.0"}
                    %
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">Loading analytics...</p>
            )}

            {analytics?.top_queries && analytics.top_queries.length > 0 && (
              <div className="mt-8">
                <h3 className="font-semibold text-secondary mb-4">Top Queries</h3>
                <div className="space-y-2">
                  {analytics.top_queries.map((q, i) => (
                    <div
                      key={i}
                      className="flex justify-between items-center py-2 px-4 rounded-lg bg-gray-50"
                    >
                      <span className="text-sm text-gray-700 truncate flex-1 mr-4">{q.query}</span>
                      <span className="text-sm font-medium text-primary">{q.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </CopilotShell>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <AdminInner />
    </RequireAuth>
  );
}
