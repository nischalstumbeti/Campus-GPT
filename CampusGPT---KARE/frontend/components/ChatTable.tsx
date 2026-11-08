"use client";

import type { ReactNode } from "react";

/** Render pipe tables in assistant answers as real HTML tables. */
export function renderMessageContent(content: string) {
  const lines = (content || "").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    const isTableStart =
      line.trim().startsWith("|") &&
      i + 1 < lines.length &&
      /^\|[\s\-:|]+\|$/.test(lines[i + 1].trim());

    if (isTableStart) {
      const header = line
        .split("|")
        .slice(1, -1)
        .map((c) => c.trim());
      i += 2; // skip separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(
          lines[i]
            .split("|")
            .slice(1, -1)
            .map((c) => c.trim())
        );
        i += 1;
      }
      // optional title: previous non-empty text line already flushed; title may be just above
      blocks.push(
        <div key={key++} className="my-2 overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full text-xs sm:text-sm text-left">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                {header.map((h, hi) => (
                  <th key={hi} className="px-3 py-2 font-semibold whitespace-nowrap border-b border-gray-200">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 ? "bg-gray-50/60" : "bg-white"}>
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-1.5 text-gray-800 whitespace-nowrap border-b border-gray-100">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // gather plain text until next table
    const buf: string[] = [];
    while (i < lines.length) {
      const nxt =
        lines[i].trim().startsWith("|") &&
        i + 1 < lines.length &&
        /^\|[\s\-:|]+\|$/.test(lines[i + 1].trim());
      if (nxt) break;
      buf.push(lines[i]);
      i += 1;
    }
    const text = buf.join("\n").replace(/\n{3,}/g, "\n\n").trim();
    if (text) {
      blocks.push(
        <p key={key++} className="text-sm whitespace-pre-wrap">
          {text}
        </p>
      );
    }
  }

  return <>{blocks}</>;
}
