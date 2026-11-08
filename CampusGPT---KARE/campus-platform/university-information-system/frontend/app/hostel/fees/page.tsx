"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Plan = {
  id: number;
  title: string;
  category: string;
  amount: number;
  deadline: string;
  notes?: string;
};

export default function HostelFeesPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<{ plans: Plan[] }>("/api/v1/fees/plans?category=hostel")
      .then((d) => setPlans(d.plans || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load hostel fee deadlines"));
  }, []);

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-[#0B2A4A] mb-1">Hostel fee deadlines</h1>
      <p className="text-sm text-slate-500 mb-6">Hostel fee plans visible to the warden. Payments are recorded in the student portal.</p>
      {error && <p className="text-sm text-red-700 mb-4">{error}</p>}
      <div className="grid gap-3">
        {plans.map((p) => (
          <article key={p.id} className="bg-white border rounded-xl p-4">
            <div className="flex justify-between gap-3">
              <h2 className="font-semibold text-[#0B2A4A]">{p.title}</h2>
              <span className="text-sm font-medium">₹{p.amount}</span>
            </div>
            <p className="text-sm text-slate-600 mt-1 capitalize">
              {p.category.replace("_", " ")} · deadline {p.deadline}
            </p>
          </article>
        ))}
        {!error && plans.length === 0 && <p className="text-sm text-slate-500">No hostel fee plans.</p>}
      </div>
    </AppShell>
  );
}
