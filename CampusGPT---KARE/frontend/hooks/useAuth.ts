"use client";

import { useEffect, useState } from "react";
import { fetchMe, clearAuth, getToken, type AuthUser } from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timedOut = false;
    const timeout = setTimeout(() => {
      if (!cancelled) {
        timedOut = true;
        setLoading(false);
        if (typeof navigator !== "undefined" && navigator.onLine === false) setOffline(true);
        else setProblem("The Campus-GPT API did not answer in time. It may still be starting.");
      }
    }, 40000);

    fetchMe()
      .then((u) => {
        if (cancelled || timedOut) return;
        setUser(u);
        setOffline(false);
      })
      .catch((err) => {
        if (cancelled || timedOut) return;
        if (typeof navigator !== "undefined" && navigator.onLine === false) setOffline(true);
        else setProblem(err instanceof Error && err.message ? err.message : "The Campus-GPT API did not respond.");
      })
      .finally(() => {
        if (!cancelled && !timedOut) setLoading(false);
        clearTimeout(timeout);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, []);

  const logout = () => {
    clearAuth();
    setUser(null);
    window.location.href = "/";
  };

  return { user, loading, logout, isLoggedIn: !!user, offline, problem, hasToken: !!getToken() };
}
