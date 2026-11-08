"use client";

import { useState } from "react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiPost } from "@/lib/api";

const RECIPIENTS = [
  "Head of Department",
  "Class Advisor",
  "Dean",
  "Principal",
  "Controller of Examinations",
  "Hostel Warden",
  "Faculty",
];

function DocumentsInner() {
  const [topic, setTopic] = useState("attend an AWS workshop");
  const [recipient, setRecipient] = useState(RECIPIENTS[0]);
  const [customRecipient, setCustomRecipient] = useState("");
  const [err, setErr] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [out, setOut] = useState<{ formal: string; email: string; short: string; disclaimer: string } | null>(null);

  const generate = async () => {
    const typed = customRecipient.trim();
    if (recipient === "other" && !typed) {
      setErr("Enter the person or designation this letter is addressed to.");
      return;
    }
    setErr("");
    const audience = recipient === "other" ? typed : `The ${recipient}`;
    setSentTo(audience);
    const d = await apiPost<typeof out>("/api/copilot/letters", { kind: "hod_permission", topic, audience });
    setOut(d);
  };

  const copy = (text: string) => navigator.clipboard.writeText(text);

  return (
    <CopilotShell title="Documents">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-primary">Document assistant</h1>
        <p className="text-sm text-gray-600 mt-1">
          Generate letter templates to copy yourself. Nothing is submitted from here.
        </p>
        <div className="mt-4 space-y-3">
          <label className="block text-sm text-gray-700">
            To whom are you drafting?
            <select
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              className="mt-1 w-full rounded-xl border px-3 py-2 text-sm text-gray-800 bg-white"
            >
              {RECIPIENTS.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
              <option value="other">Other — enter manually</option>
            </select>
          </label>
          {recipient === "other" ? (
            <label className="block text-sm text-gray-700">
              Name or designation
              <input
                value={customRecipient}
                onChange={(e) => setCustomRecipient(e.target.value)}
                placeholder="For example, Dr. Priya Raman"
                className="mt-1 w-full rounded-xl border px-3 py-2 text-sm"
              />
            </label>
          ) : null}
          <label className="block text-sm text-gray-700">
            What is the letter about?
            <input value={topic} onChange={(e) => setTopic(e.target.value)} className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" />
          </label>
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {sentTo ? <p className="text-sm text-gray-600">Addressed to: {sentTo}</p> : null}
          <button onClick={generate} className="px-4 py-2 rounded-xl bg-primary text-white text-sm">Generate</button>
        </div>
        {out && (
          <div className="mt-6 space-y-4">
            <p className="text-xs text-gray-500">{out.disclaimer}</p>
            {(["formal", "email", "short"] as const).map((k) => (
              <section key={k} className="rounded-2xl border border-gray-100 bg-white p-4">
                <div className="flex justify-between">
                  <h2 className="font-semibold text-primary capitalize">{k} version</h2>
                  <button onClick={() => copy(out[k])} className="text-xs text-primary">Copy</button>
                </div>
                <pre className="whitespace-pre-wrap text-sm text-gray-700 mt-2 font-sans">{out[k]}</pre>
              </section>
            ))}
          </div>
        )}
      </main>
    </CopilotShell>
  );
}

export default function DocumentsPage() {
  return <RequireAuth roles={["student"]}><DocumentsInner /></RequireAuth>;
}
