"use client";

import { useEffect, useId, useState } from "react";

export default function MermaidDiagram({
  chart,
  title = "Diagram",
}: {
  chart: string;
  title?: string;
}) {
  const reactId = useId().replace(/:/g, "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(false);
  const code = (chart || "").replace(/\\n/g, "\n").trim();

  useEffect(() => {
    if (!code) {
      setSvg("");
      setError(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
        const { svg: rendered } = await mermaid.render(`mmd-${reactId}`, code);
        if (!cancelled) {
          setSvg(rendered);
          setError(false);
        }
      } catch {
        if (!cancelled) {
          setSvg("");
          setError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code, reactId]);

  if (!code) return null;

  const liveUrl = `https://mermaid.live/edit#base64:${btoa(unescape(encodeURIComponent(code)))}`;

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden my-3">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-100">
        <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">{title}</span>
        <a href={liveUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline">
          Open in Mermaid Live
        </a>
      </div>
      {svg ? (
        <div className="p-3 overflow-auto max-h-80" dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <pre className="text-xs text-gray-600 overflow-auto max-h-48 p-3 bg-gray-50 font-mono whitespace-pre-wrap">
          {error ? "Could not render diagram locally. Use Mermaid Live.\n\n" : "Rendering…\n\n"}
          {code}
        </pre>
      )}
    </div>
  );
}
