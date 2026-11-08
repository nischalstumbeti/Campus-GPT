"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { INTERNET_EVENT, INTERNET_ISSUE_MESSAGE, INTERNET_OK_EVENT } from "@/lib/network";

export default function InternetBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const show = () => setVisible(true);
    const hide = () => setVisible(false);

    const onOffline = () => show();
    const onOnline = () => hide();
    const onIssue = () => show();
    const onOk = () => {
      if (typeof navigator === "undefined" || navigator.onLine) hide();
    };

    if (typeof navigator !== "undefined" && navigator.onLine === false) show();

    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    window.addEventListener(INTERNET_EVENT, onIssue);
    window.addEventListener(INTERNET_OK_EVENT, onOk);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      window.removeEventListener(INTERNET_EVENT, onIssue);
      window.removeEventListener(INTERNET_OK_EVENT, onOk);
    };
  }, []);

  if (!visible) return null;

  return (
    <div className="sticky top-0 z-[80] bg-amber-500 text-white px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2">
      <WifiOff className="w-4 h-4 shrink-0" />
      <span>{INTERNET_ISSUE_MESSAGE}</span>
    </div>
  );
}
