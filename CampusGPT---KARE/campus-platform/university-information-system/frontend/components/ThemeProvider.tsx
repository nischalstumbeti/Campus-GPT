"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { applyBrandingToDocument, DEFAULT_BRANDING, type Branding } from "@/lib/branding";

const API = process.env.NEXT_PUBLIC_UIS_API_URL || "http://localhost:8000";

type BrandingState = { branding: Branding; ready: boolean };

const BrandingContext = createContext<BrandingState>({ branding: DEFAULT_BRANDING, ready: false });

export function useBranding() {
  return useContext(BrandingContext).branding;
}

export function useBrandingReady() {
  return useContext(BrandingContext).ready;
}

export function BrandingLine({
  text,
  className = "",
  width = "w-40",
}: {
  text?: string;
  className?: string;
  width?: string;
}) {
  const ready = useBrandingReady();
  if (!ready) {
    return <span className={`inline-block h-4 ${width} rounded bg-slate-200 animate-pulse ${className}`} aria-hidden />;
  }
  if (!text) return null;
  return <span className={className}>{text}</span>;
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!ready) return;
    const title = branding.app_name || branding.header_title;
    if (title) document.title = title;
  }, [ready, branding.app_name, branding.header_title]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(`${API}/api/v1/branding`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (cancelled || !data?.branding) {
            if (!cancelled) setReady(true);
            return;
          }
          const next = { ...DEFAULT_BRANDING, ...(data.branding as Branding) };
          setBranding(next);
          applyBrandingToDocument(next);
          if (next.app_name || next.header_title) {
            document.title = next.app_name || next.header_title;
          }
          setReady(true);
        })
        .catch(() => {
          if (!cancelled) setReady(true);
        });
    };
    load();
    const onUpdate = () => load();
    window.addEventListener("uis-branding-updated", onUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener("uis-branding-updated", onUpdate);
    };
  }, []);

  return <BrandingContext.Provider value={{ branding, ready }}>{children}</BrandingContext.Provider>;
}
