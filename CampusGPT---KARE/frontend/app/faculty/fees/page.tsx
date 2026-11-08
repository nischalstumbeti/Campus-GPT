"use client";

import { useEffect, useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type Plan = {
  id: number;
  title: string;
  category: string;
  amount: number;
  deadline: string;
  notes?: string;
};

function FacultyFeesInner() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<{ plans: Plan[] }>("/api/fees/plans")
      .then((d) => setPlans(d.plans || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load fee deadlines"));
  }, []);

  return (
    <CopilotShell title="Fee deadlines">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">Fee deadlines</h1>
        <p className="text-sm text-gray-600 mt-1 mb-6">
          Published fee plans. Creating plans and recording payments stays with the admin office.
        </p>
        {error && <p className="text-sm text-red-700 mb-4">{error}</p>}
        <div className="grid gap-3">
          {plans.map((p) => (
            <article key={p.id} className="rounded-2xl border border-gray-100 bg-white p-4">
              <div className="flex justify-between gap-3">
                <h2 className="font-semibold text-primary">{p.title}</h2>
                <span className="text-sm font-medium">₹{p.amount}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1 capitalize">
                {p.category.replaceAll("_", " ")} · deadline {p.deadline}
              </p>
              {p.notes && <p className="text-xs text-gray-500 mt-1">{p.notes}</p>}
            </article>
          ))}
          {!error && plans.length === 0 && <p className="text-sm text-gray-500">No active fee plans.</p>}
        </div>
      </main>
    </CopilotShell>
  );
}

export default function FacultyFeesPage() {
  return (
    <RequireAuth roles={["faculty", "admin", "super_admin", "hostel_admin"]}>
      <FacultyFeesInner />
    </RequireAuth>
  );
}
