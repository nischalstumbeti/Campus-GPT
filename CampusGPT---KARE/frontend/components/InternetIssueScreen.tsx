"use client";

import { WifiOff } from "lucide-react";
import { INTERNET_ISSUE_MESSAGE } from "@/lib/network";

export default function InternetIssueScreen() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 text-center bg-white">
      <WifiOff className="w-10 h-10 text-amber-500 mb-3" />
      <p className="text-lg font-semibold text-gray-900">Internet issue</p>
      <p className="text-sm text-gray-600 mt-1 max-w-sm">{INTERNET_ISSUE_MESSAGE}</p>
    </div>
  );
}
