"use client";

import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";

const UIS = process.env.NEXT_PUBLIC_UIS_URL || "http://localhost:3000";

function HostelInner() {
  return (
    <CopilotShell title="Hostel">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">Hostel warden queue</h1>
        <p className="text-sm text-gray-600 mt-2 mb-6">
          Leave approvals, room allocations, and hostel complaints are recorded in the University Information System.
          This assistant does not keep a second copy of those decisions.
        </p>
        <div className="grid gap-3">
          <a
            href={`${UIS}/hostel/leaves`}
            className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/40"
          >
            <p className="font-semibold text-primary">Leave approvals</p>
            <p className="text-sm text-gray-600 mt-1">Open the warden leave queue in UIS.</p>
          </a>
          <a
            href={`${UIS}/hostel/rooms`}
            className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/40"
          >
            <p className="font-semibold text-primary">Room allocations</p>
            <p className="text-sm text-gray-600 mt-1">See who is assigned to each room.</p>
          </a>
          <a
            href={`${UIS}/hostel/complaints`}
            className="rounded-2xl border border-gray-100 bg-white p-4 hover:border-primary/40"
          >
            <p className="font-semibold text-primary">Hostel complaints</p>
            <p className="text-sm text-gray-600 mt-1">Update room, mess, and facility issues.</p>
          </a>
        </div>
      </main>
    </CopilotShell>
  );
}

export default function HostelPage() {
  return (
    <RequireAuth roles={["hostel_admin", "admin", "super_admin"]}>
      <HostelInner />
    </RequireAuth>
  );
}
