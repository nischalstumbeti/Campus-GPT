"use client";

import AppShell from "@/components/AppShell";
import ComplaintInbox from "@/components/ComplaintInbox";

export default function FacultyComplaintsPage() {
  return (
    <AppShell>
      <ComplaintInbox
        title="Student complaints"
        subtitle="Academic / general complaints from students. Hostel-only issues are handled by the warden."
      />
    </AppShell>
  );
}
