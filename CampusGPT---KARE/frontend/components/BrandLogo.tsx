"use client";

import Image from "next/image";
import { useBranding } from "@/components/ThemeProvider";

export default function BrandLogo({ size = 32, className = "" }: { size?: number; className?: string }) {
  const branding = useBranding();
  if (branding.logo_url) {
    return (
      <img
        src={branding.logo_url}
        alt=""
        width={size}
        height={size}
        className={`object-contain ${className}`}
      />
    );
  }
  return <Image src="/kare-logo.png" alt="KARE" width={size} height={size} className={`object-contain ${className}`} />;
}
