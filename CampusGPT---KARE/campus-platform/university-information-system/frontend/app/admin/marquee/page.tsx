"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminMarqueeRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/cms?tab=marquee");
  }, [router]);
  return <p className="p-8 text-sm text-slate-500">Opening Admin CMS…</p>;
}
