"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import InternetIssueScreen from "@/components/InternetIssueScreen";

export default function RequireAuth({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: string[];
}) {
  const { user, loading, offline, problem, hasToken } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (offline && hasToken) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/workspace")}`);
      return;
    }
    if (roles && roles.length && !roles.includes(user.role)) {
      router.replace("/workspace");
    }
  }, [user, loading, roles, router, pathname, offline, hasToken]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        Checking sign-in...
      </div>
    );
  }
  if (offline && hasToken && !user) {
    return <InternetIssueScreen />;
  }
  if (problem && hasToken && !user) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6 text-center">
        <p className="text-sm text-gray-700 max-w-md">{problem}</p>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500 text-sm">
        Checking sign-in...
      </div>
    );
  }
  if (roles && roles.length && !roles.includes(user.role)) {
    return null;
  }
  return <>{children}</>;
}
