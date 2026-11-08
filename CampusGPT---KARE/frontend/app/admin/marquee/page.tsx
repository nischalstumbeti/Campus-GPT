"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy path — branding + marquee live under Admin CMS. */
export default function AdminMarqueeRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/cms?tab=marquee");
  }, [router]);
  return <p className="p-8 text-sm text-gray-500">Opening Admin CMS…</p>;
}
