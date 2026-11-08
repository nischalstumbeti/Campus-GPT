"use client";

import { FormEvent, useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import SyncBadge from "@/components/SyncBadge";
import { useAuth } from "@/hooks/useAuth";
import { apiGet, apiPost, apiPut } from "@/lib/api";

const UIS_URL = process.env.NEXT_PUBLIC_UIS_URL || "http://localhost:3000";

type Prefs = {
  email_messages: boolean;
  email_fees: boolean;
  email_leave: boolean;
  inapp_messages: boolean;
  inapp_fees: boolean;
  inapp_leave: boolean;
};

type LinkStatus = {
  uis_enabled: boolean;
  uis_linked: boolean;
  uis_username?: string | null;
  source?: string;
};

function SettingsInner() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [pwdSource, setPwdSource] = useState<string>("");
  const [link, setLink] = useState<LinkStatus | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);

  useEffect(() => {
    apiGet<LinkStatus>("/api/me/link-status").then(setLink).catch(() => null);
    apiGet<Prefs>("/api/me/notification-prefs").then(setPrefs).catch(() => null);
  }, []);

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    setMsg("");
    setErr("");
    if (newPassword.length < 6) {
      setErr("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirm) {
      setErr("New password and confirmation do not match.");
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<{ message: string; synced_to_uis?: boolean; source?: string }>(
        "/api/auth/change-password",
        { current_password: currentPassword, new_password: newPassword }
      );
      setMsg(res.message || "Password updated.");
      setPwdSource(res.source || (res.synced_to_uis ? "UIS" : "local"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  };

  const savePrefs = async (next: Prefs) => {
    setPrefs(next);
    await apiPut("/api/me/notification-prefs", next).catch(() => null);
  };

  return (
    <CopilotShell title="Settings">
      <main className="max-w-xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-primary">Settings</h1>
          <p className="text-sm text-gray-600 mt-2">
            {user?.full_name} · {user?.email} · {user?.role}
          </p>
        </div>

        <section className="rounded-2xl border border-gray-100 bg-white p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-primary">Account link (SSO)</h2>
            <SyncBadge source={link?.source} />
          </div>
          {link?.uis_linked ? (
            <p className="text-sm text-gray-600 mt-2">
              Linked as <span className="font-medium">{link.uis_username}</span>. One password works for Campus-GPT
              and KARE UIS when you change it below.
            </p>
          ) : (
            <p className="text-sm text-gray-600 mt-2">
              Not linked yet. Sign in with your UIS username / institutional email so leave, fees, and academics stay
              shared.
            </p>
          )}
          <a href={UIS_URL} className="inline-block mt-3 text-sm text-primary hover:underline">
            Open KARE UIS
          </a>
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold text-primary">Change password</h2>
            {pwdSource && <SyncBadge source={pwdSource} />}
          </div>
          <form onSubmit={changePassword} className="mt-4 space-y-3">
            <input
              type="password"
              required
              autoComplete="current-password"
              className="w-full border rounded-xl px-3 py-2 text-sm"
              placeholder="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <input
              type="password"
              required
              autoComplete="new-password"
              className="w-full border rounded-xl px-3 py-2 text-sm"
              placeholder="New password (min 6 characters)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <input
              type="password"
              required
              autoComplete="new-password"
              className="w-full border rounded-xl px-3 py-2 text-sm"
              placeholder="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            {err && <p className="text-sm text-red-600">{err}</p>}
            {msg && <p className="text-sm text-emerald-700">{msg}</p>}
            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 rounded-xl bg-primary text-white text-sm font-medium disabled:opacity-60"
            >
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5">
          <h2 className="font-semibold text-primary">Notification preferences</h2>
          <p className="text-sm text-gray-600 mt-1">Choose email and in-app alerts for fees and messages.</p>
          {prefs && (
            <div className="mt-3 space-y-2 text-sm">
              {(
                [
                  ["email_messages", "Email when I get a message"],
                  ["email_fees", "Email fee reminders"],
                  ["email_leave", "Email leave status updates"],
                  ["inapp_messages", "In-app message alerts"],
                  ["inapp_fees", "In-app fee alerts"],
                  ["inapp_leave", "In-app leave status alerts"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 text-gray-700">
                  <input
                    type="checkbox"
                    checked={!!prefs[key]}
                    onChange={(e) => savePrefs({ ...prefs, [key]: e.target.checked })}
                  />
                  {label}
                </label>
              ))}
            </div>
          )}
        </section>
      </main>
    </CopilotShell>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsInner />
    </RequireAuth>
  );
}
