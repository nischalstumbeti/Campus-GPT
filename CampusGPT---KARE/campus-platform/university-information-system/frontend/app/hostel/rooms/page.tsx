"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Alloc = {
  student_id: string;
  name: string;
  hostel: string;
  block: string;
  room: string;
  bed: string;
  status: string;
};

export default function HostelRoomsPage() {
  const [rows, setRows] = useState<Alloc[]>([]);
  useEffect(() => {
    apiFetch<{ allocations: Alloc[] }>("/api/v1/hostel/allocations")
      .then((d) => setRows(d.allocations || []))
      .catch(() => setRows([]));
  }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-bold text-[#0B2A4A] mb-1">Room allocations</h1>
      <p className="text-sm text-slate-500 mb-4">
        Active hostel occupancy managed by the warden office.
      </p>
      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Hostel</th>
              <th className="px-3 py-2">Block / Room</th>
              <th className="px-3 py-2">Bed</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={`${a.student_id}-${a.room}`} className="border-t">
                <td className="px-3 py-2">
                  <Link href={`/hostel/students/${a.student_id}`} className="font-medium text-[#0B2A4A] underline">
                    {a.name}
                  </Link>
                  <p className="text-xs">
                    <Link href={`/hostel/students/${a.student_id}`} className="text-[#0B2A4A] underline">
                      {a.student_id}
                    </Link>
                  </p>
                </td>
                <td className="px-3 py-2">{a.hostel}</td>
                <td className="px-3 py-2">
                  {a.block} · {a.room}
                </td>
                <td className="px-3 py-2">{a.bed}</td>
                <td className="px-3 py-2 capitalize">{a.status}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-slate-400">
                  No allocations found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
