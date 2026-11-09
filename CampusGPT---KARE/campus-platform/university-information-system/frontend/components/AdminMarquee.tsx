"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { sanitizeNoticeHtml } from "@/lib/noticeHtml";

type Item = { id: number; description: string };

/** Campus-wide scrolling notices from Admin CMS. Visible on the sign-in page and every role. */
export default function AdminMarquee() {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(`${API}/api/v1/admin/marquee/active`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (cancelled) return;
          const rows = ((data?.items || []) as Item[]).filter((item) => (item.description || "").trim());
          setItems(rows);
        })
        .catch(() => {
          if (!cancelled) setItems([]);
        });
    };
    load();
    window.addEventListener("uis-marquee-updated", load);
    window.addEventListener("focus", load);
    return () => {
      cancelled = true;
      window.removeEventListener("uis-marquee-updated", load);
      window.removeEventListener("focus", load);
    };
  }, []);

  if (!items.length) return null;

  const track = [...items, ...items];

  return (
    <div className="admin-marquee relative z-20 border-b border-amber-200 bg-amber-50 text-amber-950" role="status">
      <div className="admin-marquee-track">
        {track.map((item, i) => (
          <span
            key={`${item.id}-${i}`}
            className="admin-marquee-item"
            dangerouslySetInnerHTML={{ __html: sanitizeNoticeHtml(item.description) }}
          />
        ))}
      </div>
    </div>
  );
}
