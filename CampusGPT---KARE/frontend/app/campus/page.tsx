"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export default function CampusRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getToken() ? "/workspace" : "/login?next=/workspace");
  }, [router]);
  return <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Opening your workspace...</div>;
}
