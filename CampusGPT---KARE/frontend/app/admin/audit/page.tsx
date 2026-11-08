"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Item = {
  id: number;
  actor_email: string;
  actor_role: string;
  action: string;
  resource: string;
  detail: string;
  created_at?: string;
};

function Inner() {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    apiGet<{ items: Item[] }>("/api/admin/audit").then((d) => setItems(d.items || [])).catch(() => setItems([]));
  }, []);

  return (
    <CopilotShell title="Audit">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary mb-1">Audit trail</h1>
        <p className="text-sm text-gray-600 mb-4">Password, fees, marquee, leave confirms, and exports.</p>
        <div className="rounded-2xl border border-gray-100 bg-white overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-gray-50 text-xs text-gray-500 text-left">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Actor</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Resource</th>
                  <th className="px-3 py-2">Detail</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="px-3 py-2 text-xs whitespace-nowrap">{r.created_at?.slice(0, 19).replace("T", " ")}</td>
                    <td className="px-3 py-2">
                      <p className="truncate max-w-[160px]">{r.actor_email || "—"}</p>
                      <p className="text-[11px] text-gray-400 capitalize">{r.actor_role}</p>
                    </td>
                    <td className="px-3 py-2 font-medium">{r.action}</td>
                    <td className="px-3 py-2">{r.resource}</td>
                    <td className="px-3 py-2 text-xs text-gray-600 max-w-[220px] truncate">{r.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!items.length && <p className="p-6 text-sm text-gray-400 text-center">No audit events yet.</p>}
        </div>
      </div>
    </CopilotShell>
  );
}

export default function AuditPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <Inner />
    </RequireAuth>
  );
}
