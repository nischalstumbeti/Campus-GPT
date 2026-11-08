"use client";

import AppShell from "@/components/AppShell";
import ComplaintInbox from "@/components/ComplaintInbox";

export default function HostelComplaintsPage() {
  return (
    <AppShell>
      <ComplaintInbox
        title="Hostel complaints"
        subtitle="Room, mess, and facility issues from students. Academic complaints are handled by faculty."
      />
    </AppShell>
  );
}
