"use client";

import { useEffect, useState } from "react";
import { fetchMe, clearAuth, getToken, type AuthUser } from "@/lib/auth";
import { isInternetIssue } from "@/lib/network";

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timedOut = false;
    const timeout = setTimeout(() => {
      if (!cancelled) {
        timedOut = true;
        setLoading(false);
        setOffline(true);
      }
    }, 12000);

    fetchMe()
      .then((u) => {
        if (cancelled || timedOut) return;
        setUser(u);
        setOffline(false);
      })
      .catch((err) => {
        if (cancelled || timedOut) return;
        if (isInternetIssue(err)) setOffline(true);
        else setUser(null);
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

  return { user, loading, logout, isLoggedIn: !!user, offline, hasToken: !!getToken() };
}
