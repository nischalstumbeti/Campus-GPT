"use client";

import { useEffect } from "react";
import { applyBrandingToDocument, DEFAULT_BRANDING, type Branding } from "@/lib/branding";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    let cancelled = false;
    applyBrandingToDocument(DEFAULT_BRANDING);
    fetch(`${API_BASE}/api/branding`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data?.branding) return;
        applyBrandingToDocument({ ...DEFAULT_BRANDING, ...(data.branding as Branding) });
      })
      .catch(() => {
        /* keep defaults */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <>{children}</>;
}
