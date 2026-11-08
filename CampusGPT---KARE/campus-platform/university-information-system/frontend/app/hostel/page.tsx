"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Dash = {
  welcome: string;
  role: string;
  title?: string;
  pending_leaves: number;
  approved_leaves: number;
  rejected_leaves: number;
  active_allocations?: number;
  open_hostel_complaints?: number;
};

export default function HostelDashboard() {
  const [data, setData] = useState<Dash | null>(null);
  useEffect(() => {
    apiFetch<Dash>("/api/v1/hostel/dashboard").then(setData).catch(() => setData(null));
  }, []);

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-[#0B2A4A] mb-1">{data?.welcome || "Hostel Warden"}</h1>
      <p className="text-sm text-slate-500 mb-6">
        {data?.title || "Hostel Warden Office"} · leave, rooms, and hostel complaints
      </p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500">Pending leave</p>
          <p className="text-3xl font-semibold text-amber-600">{data?.pending_leaves ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500">Room allocations</p>
          <p className="text-3xl font-semibold text-[#0B2A4A]">{data?.active_allocations ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500">Open hostel complaints</p>
          <p className="text-3xl font-semibold text-red-600">{data?.open_hostel_complaints ?? "—"}</p>
        </div>
        <div className="bg-white border rounded-xl p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-500">Approved leave</p>
          <p className="text-3xl font-semibold text-emerald-700">{data?.approved_leaves ?? "—"}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/hostel/leaves"
          className="inline-flex items-center rounded-lg bg-[#0B2A4A] text-white text-sm font-medium px-4 py-2.5 hover:bg-[#163A5C]"
        >
          Leave approvals →
        </Link>
        <Link
          href="/hostel/rooms"
          className="inline-flex items-center rounded-lg border border-[#0B2A4A] text-[#0B2A4A] text-sm font-medium px-4 py-2.5"
        >
          Room allocations →
        </Link>
        <Link
          href="/hostel/complaints"
          className="inline-flex items-center rounded-lg border border-[#0B2A4A] text-[#0B2A4A] text-sm font-medium px-4 py-2.5"
        >
          Hostel complaints →
        </Link>
      </div>
    </AppShell>
  );
}
