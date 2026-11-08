"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

type Item = { id: number; icon: string; description: string };

/** Campus-wide scrolling ticker — visible to every signed-in role. */
export default function AdminMarquee() {
  const { user } = useAuth();
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    if (!user) return;
    // Public active endpoint (any signed-in role); falls back to admin path for older deploys
    apiGet<{ items: Item[] }>("/api/marquee/active")
      .then((d) => setItems(d.items || []))
      .catch(() =>
        apiGet<{ items: Item[] }>("/api/admin/marquee/active")
          .then((d) => setItems(d.items || []))
          .catch(() => setItems([]))
      );
  }, [user]);

  if (!user || !items.length) return null;

  const track = [...items, ...items];

  return (
    <div className="admin-marquee border-b border-amber-200 bg-amber-50 text-amber-950">
      <div className="admin-marquee-track">
        {track.map((item, i) => (
          <span key={`${item.id}-${i}`} className="admin-marquee-item">
            <span className="admin-marquee-icon" aria-hidden>
              {item.icon}
            </span>
            {item.description}
          </span>
        ))}
      </div>
    </div>
  );
}
