"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import AdminMarquee from "@/components/AdminMarquee";
import { useBranding, useBrandingReady } from "@/components/ThemeProvider";
import { API } from "@/lib/api";
import { sanitizeNoticeHtml } from "@/lib/noticeHtml";

const LOGIN_TIMEOUT_MS = API.startsWith("http://localhost") || API.startsWith("http://127.0.0.1") ? 12000 : 60000;

async function loginRequest(username: string, password: string, timeoutMs = LOGIN_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      signal: controller.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Invalid credentials";
      throw new Error(detail);
    }
    return data as { access_token: string; role: string; full_name: string; username: string };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`UIS API timed out (${API}). The server may be waking up. Try again in a few seconds.`);
    }
    if (err instanceof TypeError) {
      throw new Error(
        `Cannot reach UIS API${API ? ` at ${API}` : ""}. It may still be waking up. Try again in a few seconds.`
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export default function LoginPage() {
  const router = useRouter();
  const branding = useBranding();
  const ready = useBrandingReady();
  const loginBg = branding.login_background_url || branding.background_image_url;
  const title = branding.header_title || branding.app_name;
  const [username, setUsername] = useState("student.demo");
  const [password, setPassword] = useState("campus123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await loginRequest(username.trim(), password);
      localStorage.setItem("uis_token", data.access_token);
      const next = new URLSearchParams(window.location.search).get("next");
      const gpt = process.env.NEXT_PUBLIC_CAMPUS_GPT_URL || "http://localhost:3001";
      if (next === "campus-gpt") {
        // Hash fragment keeps the token out of server/proxy query logs
        window.location.href = `${gpt}/login#uis_token=${encodeURIComponent(data.access_token)}`;
        return;
      }
      const role = (data.role || "").toLowerCase();
      if (role === "student") router.push("/student");
      else if (role === "faculty" || role === "hod" || role === "school_dean") router.push("/faculty");
      else if (role === "hostel_admin" || role === "warden" || role === "hostel_warden") router.push("/hostel");
      else router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const quick = (user: string) => {
    setUsername(user);
    setPassword("campus123");
    setError("");
  };

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden">
      <AdminMarquee />
      {loginBg ? (
        <div
          className="absolute inset-0 bg-cover bg-center bg-no-repeat"
          style={{ backgroundImage: `url("${loginBg.replace(/"/g, "")}")` }}
          aria-hidden
        />
      ) : null}
      <div className="absolute inset-0" style={{ backgroundColor: ready ? branding.primary : "#e2e8f0", opacity: loginBg ? 0.35 : 1 }} aria-hidden />

      <div className="relative flex-1 flex items-center justify-end px-4 sm:px-8 lg:px-16 py-10">
        <div className="w-full max-w-md bg-white/95 backdrop-blur-sm border border-slate-200 rounded-2xl shadow-xl p-8 mr-0 lg:mr-8">
          <div className="flex items-center gap-3 mb-4">
            {!ready ? (
              <span className="h-[52px] w-[52px] rounded-md bg-slate-200 animate-pulse" aria-hidden />
            ) : branding.logo_url ? (
              <img src={branding.logo_url} alt="" className="h-[52px] w-[52px] object-contain" />
            ) : null}
            <div className="min-w-0 flex-1">
              {!ready ? (
                <>
                  <span className="block h-5 w-48 rounded bg-slate-200 animate-pulse" aria-hidden />
                  <span className="mt-2 block h-3 w-64 rounded bg-slate-100 animate-pulse" aria-hidden />
                </>
              ) : (
                <>
                  <h1 className="text-lg font-bold leading-tight" style={{ color: branding.primary }}>
                    {title}
                  </h1>
                  {branding.header_subtitle ? (
                    <p className="text-xs text-slate-500 mt-0.5">{branding.header_subtitle}</p>
                  ) : null}
                </>
              )}
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-6">{ready ? branding.sign_in_label || "Sign in" : " "}</p>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Username or email</label>
              <input
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0B2A4A]/30"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Password</label>
              <input
                type="password"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0B2A4A]/30"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            {error && <p className="text-sm text-red-600 whitespace-pre-wrap">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-60"
              style={{ backgroundColor: branding.primary }}
            >
              {loading ? "Signing in…" : ready ? branding.sign_in_label || "Sign in" : "…"}
            </button>
          </form>
          <div className="mt-6 text-xs text-slate-500 space-y-2 border-t pt-4">
            <p className="font-medium text-slate-700">Demo login (password: campus123)</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                ["student.demo", "Student"],
                ["faculty.demo", "Faculty"],
                ["warden.demo", "Warden"],
                ["admin.demo", "Admin"],
              ].map(([user, label]) => (
                <button
                  key={user}
                  type="button"
                  onClick={() => quick(user)}
                  className="rounded-md border border-slate-200 px-2 py-1.5 text-left hover:bg-slate-50"
                >
                  <span className="block font-medium text-[#0B2A4A]">{label}</span>
                  <span className="text-[10px] text-slate-400">{user}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {( !ready || branding.footer_text) && (
        <footer className="relative z-10 w-full px-4 py-3 text-center bg-black/25 backdrop-blur-sm border-t border-white/15">
          {!ready ? (
            <span className="inline-block h-3 w-72 rounded bg-white/40 animate-pulse" aria-hidden />
          ) : (
            <p
              className="text-[11px] sm:text-xs text-white/90 leading-relaxed [&_a]:underline [&_a]:text-white"
              dangerouslySetInnerHTML={{ __html: sanitizeNoticeHtml(branding.footer_text) }}
            />
          )}
        </footer>
      )}
    </div>
  );
}
