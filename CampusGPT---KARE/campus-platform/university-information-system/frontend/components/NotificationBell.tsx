"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type Note = {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  read: boolean;
  created_at?: string;
};

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    apiFetch<{ unread: number; items: Note[] }>("/api/v1/notifications")
      .then((d) => {
        setItems(d.items || []);
        setUnread(d.unread || 0);
      })
      .catch(() => {
        setItems([]);
        setUnread(0);
      });
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(load, 8000);
    return () => clearInterval(poll);
  }, [load]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const markAll = async () => {
    await apiFetch("/api/v1/notifications/read-all", { method: "POST" }).catch(() => null);
    setUnread(0);
    setItems((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-[#0B2A4A] hover:bg-slate-50"
        aria-label="Notifications"
      >
        Alerts
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] rounded-full bg-rose-600 text-white text-[10px] flex items-center justify-center px-1">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100">
            <p className="text-sm font-semibold text-[#0B2A4A]">Notifications</p>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="text-xs text-[#0B2A4A] underline">
                Mark all read
              </button>
            )}
          </div>
          {!items.length && <p className="px-3 py-4 text-sm text-slate-500">No notifications yet.</p>}
          {items.map((n) => (
            <Link
              key={n.id}
              href={n.link || "/messages"}
              onClick={async () => {
                setOpen(false);
                if (!n.read) {
                  await apiFetch(`/api/v1/notifications/${n.id}/read`, { method: "POST" }).catch(() => null);
                  load();
                }
              }}
              className={`block px-3 py-2.5 border-b border-slate-50 hover:bg-slate-50 ${n.read ? "" : "bg-amber-50/60"}`}
            >
              <p className="text-sm font-medium text-[#0B2A4A]">{n.title}</p>
              <p className="text-xs text-slate-600 line-clamp-2 mt-0.5">{n.body}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
