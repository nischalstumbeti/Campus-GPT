"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, LogIn, Mail, Lock } from "lucide-react";
import CloudBackground from "@/components/CloudBackground";
import { setToken, afterLoginPath } from "@/lib/auth";
import { apiFetch, INTERNET_ISSUE_MESSAGE, userFacingError } from "@/lib/network";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";
const UIS_URL = process.env.NEXT_PUBLIC_UIS_URL || "http://localhost:3000";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading sign-in…</div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ssoBusy, setSsoBusy] = useState(false);

  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
    const hashParams = new URLSearchParams(hash);
    // Tokens only from URL hash (never query string — avoids proxy/access logs)
    const token = hashParams.get("token");
    const uisToken = hashParams.get("uis_token");
    const err = searchParams.get("error");
    if (token) {
      localStorage.setItem("campus_gpt_token", token);
      if (typeof window !== "undefined" && window.location.hash) {
        history.replaceState(null, "", window.location.pathname + window.location.search);
      }
      let role = "student";
      try {
        const mid = token.split(".")[1];
        if (mid) {
          const json = JSON.parse(atob(mid.replace(/-/g, "+").replace(/_/g, "/")));
          role = json.role || role;
        }
      } catch {
        /* keep default */
      }
      router.replace(afterLoginPath(role));
      router.refresh();
      return;
    }
    if (uisToken) {
      if (typeof window !== "undefined" && window.location.hash) {
        history.replaceState(null, "", window.location.pathname + window.location.search);
      }
      setSsoBusy(true);
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 12000);
      apiFetch(`${API_BASE}/api/auth/uis-exchange`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uis_token: uisToken }),
        signal: ctrl.signal,
      })
        .then(async (res) => {
          const data = await res.json();
          if (!res.ok) {
            const d = data.detail;
            throw new Error(typeof d === "string" ? d : "UIS sign-in failed");
          }
          setToken(data.access_token);
          router.replace(afterLoginPath(data.role));
          router.refresh();
        })
        .catch((e) => {
          setError(userFacingError(e, "UIS sign-in failed"));
          router.replace("/login");
        })
        .finally(() => {
          clearTimeout(timer);
          setSsoBusy(false);
        });
      return;
    }
    if (err) {
      const msg =
        err === "google_not_configured"
          ? "Google sign-in is not configured yet."
          : err === "domain_not_allowed"
            ? "Only @klu.ac.in Google accounts can sign in."
            : err === "email_not_verified"
              ? "Your Google email is not verified. Use a verified @klu.ac.in account."
              : err === "access_denied"
                ? "Access was denied."
                : "Sign-in failed. Please try again.";
      setError(msg);
      router.replace("/login");
    }
  }, [searchParams, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");
      setToken(data.access_token);
      const next = searchParams.get("next");
      router.push(next || afterLoginPath(data.role));
      router.refresh();
    } catch (err) {
      setError(userFacingError(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setError(INTERNET_ISSUE_MESSAGE);
      return;
    }
    window.location.href = `${API_BASE}/api/auth/google`;
  };

  const handleUisSso = () => {
    window.location.href = `${UIS_URL}/login?next=campus-gpt`;
  };

  const demoRoleLogin = async (role: "student" | "faculty" | "admin") => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`${API_BASE}/api/demo/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Demo login failed");
      setToken(data.access_token);
      router.push(afterLoginPath(data.role));
      router.refresh();
    } catch (err) {
      setError(userFacingError(err, "Demo login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen font-sans flex flex-col relative overflow-hidden login-themed-bg">
      <CloudBackground variant="form" />
      <div className="flex-1 flex items-center justify-center px-6 py-12 relative z-10">
        <div className="w-full max-w-md">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-primary mb-8 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            Back to home
          </Link>

          <div className="rounded-2xl bg-white border border-gray-200 shadow-xl shadow-gray-200/50 p-8">
            <div className="flex items-center gap-3 mb-6">
              <Image src="/kare-logo.png" alt="KARE" width={48} height={48} className="object-contain" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">Welcome back</h1>
                <p className="text-sm text-gray-500">Sign in to Campus-GPT · KARE</p>
              </div>
            </div>

            {ssoBusy && (
              <p className="text-sm text-primary mb-4">Connecting your KARE UIS session…</p>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email or UIS username</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="student.demo or name@klu.ac.in"
                    className="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary bg-gray-50/50"
                    required
                    autoComplete="username"
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="block text-sm font-medium text-gray-700">Password</label>
                  <Link href="/forgot-password" className="text-sm text-primary hover:underline">
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary bg-gray-50/50"
                    required
                    autoComplete="current-password"
                  />
                </div>
              </div>
              {error && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
              )}
              <button
                type="submit"
                disabled={loading || ssoBusy}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-primary text-white font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-md shadow-primary/25"
              >
                <LogIn className="w-5 h-5" />
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <button
              type="button"
              onClick={handleUisSso}
              className="mt-3 w-full flex items-center justify-center gap-2 py-3 rounded-lg border-2 border-[#0B2A4A] text-[#0B2A4A] font-medium hover:bg-[#0B2A4A]/5"
            >
              Sign in with KARE UIS
            </button>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-3 bg-white text-gray-500">or continue with</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center gap-3 py-3 rounded-lg border-2 border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors font-medium text-gray-700"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Sign in with Google (@klu.ac.in only)
            </button>

            <div className="mt-4">
              <p className="text-[11px] text-center text-gray-500 mb-2">One-click demo roles</p>
              <div className="grid grid-cols-3 gap-2">
                <button type="button" disabled={loading} onClick={() => demoRoleLogin("student")} className="text-xs py-2 rounded-lg bg-primary/10 text-primary font-medium">
                  Student
                </button>
                <button type="button" disabled={loading} onClick={() => demoRoleLogin("faculty")} className="text-xs py-2 rounded-lg bg-primary/10 text-primary font-medium">
                  Faculty
                </button>
                <button type="button" disabled={loading} onClick={() => demoRoleLogin("admin")} className="text-xs py-2 rounded-lg bg-primary/10 text-primary font-medium">
                  Admin
                </button>
              </div>
            </div>
            <p className="mt-2 text-[11px] text-center text-gray-400">
              Or fill campus123 accounts: student.demo@klu.ac.in · admin@example.com
            </p>
          </div>

          <p className="mt-6 text-center text-sm text-gray-600">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-medium text-primary hover:underline">
              Sign up
            </Link>
            {" · "}
            <a href={UIS_URL} className="font-medium text-primary hover:underline">
              KARE UIS
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
