"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

export default function AuditPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    apiFetch("/api/v1/admin/audit-logs").then(setData);
  }, []);
  return (
    <AppShell>
      <h1 className="text-xl font-bold text-brand mb-4">Audit Logs</h1>
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Actor</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Resource</th>
              <th className="px-3 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((a: any, i: number) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-2 whitespace-nowrap text-xs">{a.timestamp}</td>
                <td className="px-3 py-2">{a.actor}</td>
                <td className="px-3 py-2">{a.user}</td>
                <td className="px-3 py-2">
                  {a.action} {a.resource}
                </td>
                <td className="px-3 py-2 font-medium">{a.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
