"use client";

import CopilotShell from "@/components/CopilotShell";

export default function WorkspaceNav({ title }: { title?: string }) {
  return (
    <div className="md:hidden">
      <p className="px-4 py-2 text-sm font-semibold text-primary">{title}</p>
    </div>
  );
}

export { CopilotShell };
