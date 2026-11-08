"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Note = {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  read: boolean;
  created_at?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const [toast, setToast] = useState<Note | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    apiGet<{ unread: number; items: Note[] }>("/api/notifications")
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
    const token = localStorage.getItem("campus_gpt_token");
    if (!token) return;
    const wsUrl = API_BASE.replace(/^http/, "ws") + `/api/messages/ws`;
    const proto =
      "cgpt." +
      btoa(token)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl, [proto]);
      ws.onopen = () => {
        // Protocol auth preferred; keep first-message auth as fallback
        try {
          ws.send(JSON.stringify({ type: "auth", token }));
        } catch {
          /* ignore */
        }
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "notification" && data.notification) {
            const n = data.notification as Note;
            setToast(n);
            setUnread((u) => u + 1);
            setItems((prev) => [n, ...prev].slice(0, 40));
            setTimeout(() => setToast((t) => (t?.id === n.id ? null : t)), 6000);
          } else if (data.type === "message" || data.type === "thread_created") {
            load();
          }
        } catch {
          // ignore
        }
      };
    } catch {
      return;
    }
    return () => ws.close();
  }, [load]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const markAll = async () => {
    await apiPost("/api/notifications/read-all", {}).catch(() => null);
    setUnread(0);
    setItems((prev) => prev.map((i) => ({ ...i, read: true })));
  };

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) load();
        }}
        className="relative p-2 rounded-lg text-gray-600 hover:bg-primary/10 hover:text-primary"
        title="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-80 max-h-96 overflow-y-auto rounded-xl border border-gray-100 bg-white shadow-lg z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-50">
            <p className="text-sm font-semibold text-primary">Notifications</p>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="text-[11px] text-primary underline">
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 && <p className="text-xs text-gray-400 px-3 py-6 text-center">No notifications yet.</p>}
          <ul>
            {items.map((n) => (
              <li key={n.id} className={`border-b border-gray-50 ${n.read ? "bg-white" : "bg-primary/5"}`}>
                <Link
                  href={n.link || "/messages"}
                  onClick={async () => {
                    setOpen(false);
                    if (!n.read) {
                      await apiPost(`/api/notifications/${n.id}/read`, {}).catch(() => null);
                      load();
                    }
                  }}
                  className="block px-3 py-2.5 hover:bg-gray-50"
                >
                  <p className="text-sm font-medium text-gray-900">{n.title}</p>
                  <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">{n.body}</p>
                  <p className="text-[10px] text-gray-400 mt-1">{n.created_at?.slice(0, 16).replace("T", " ")}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-4 right-4 z-[60] max-w-sm rounded-xl border border-primary/20 bg-white shadow-lg px-4 py-3">
          <p className="text-sm font-semibold text-primary">{toast.title}</p>
          <p className="text-xs text-gray-600 mt-1 line-clamp-2">{toast.body}</p>
          <Link href={toast.link || "/messages"} className="text-xs text-primary underline mt-2 inline-block" onClick={() => setToast(null)}>
            Open messages
          </Link>
        </div>
      )}
    </div>
  );
}
