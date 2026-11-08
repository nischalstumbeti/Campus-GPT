"use client";

import { FormEvent, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

export default function SettingsPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

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
      const res = await apiFetch<{ message: string }>("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setMsg(res.message || "Password updated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand mb-1">Settings</h1>
      <p className="text-sm text-slate-600 mb-4">
        Change your own password. It updates the institutional UIS account used for Campus-GPT and admin login.
      </p>

      <form onSubmit={changePassword} className="max-w-md bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <h2 className="font-semibold text-brand text-sm">Change password</h2>
        <input
          type="password"
          required
          autoComplete="current-password"
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="Current password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
        <input
          type="password"
          required
          autoComplete="new-password"
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="New password (min 6 characters)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <input
          type="password"
          required
          autoComplete="new-password"
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {err && <p className="text-sm text-rose-600">{err}</p>}
        {msg && <p className="text-sm text-emerald-700">{msg}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2 bg-brand text-white rounded-md text-sm disabled:opacity-60"
        >
          {busy ? "Updating…" : "Update password"}
        </button>
      </form>
    </AppShell>
  );
}
