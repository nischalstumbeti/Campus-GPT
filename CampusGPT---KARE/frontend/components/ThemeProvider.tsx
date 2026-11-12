"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { applyBrandingToDocument, DEFAULT_BRANDING, type Branding } from "@/lib/branding";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

const BrandingContext = createContext<Branding>(DEFAULT_BRANDING);

export function useBranding() {
  return useContext(BrandingContext);
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);

  useEffect(() => {
    let cancelled = false;
    applyBrandingToDocument(DEFAULT_BRANDING);
    fetch(`${API_BASE}/api/branding`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data?.branding) return;
        const next = { ...DEFAULT_BRANDING, ...(data.branding as Branding) };
        setBranding(next);
        applyBrandingToDocument(next);
      })
      .catch(() => {
        /* keep defaults */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}
