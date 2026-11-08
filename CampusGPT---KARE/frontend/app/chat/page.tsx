"use client";

import ChatInterface from "@/components/ChatInterface";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";

function ChatInner() {
  return (
    <CopilotShell title="Chat" fill>
      <ChatInterface />
    </CopilotShell>
  );
}

export default function ChatPage() {
  return (
    <RequireAuth>
      <ChatInner />
    </RequireAuth>
  );
}
