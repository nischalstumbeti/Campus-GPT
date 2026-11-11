"use client";

import { API, getToken } from "@/lib/api";

export type FillField = { key: string; label: string; type: string; required: boolean; options: string[]; show_if?: string };

export function fieldVisible(field: FillField, answers: Record<string, string>) {
  const rule = field.show_if || "";
  if (!rule.includes("=")) return true;
  const [key, expected] = rule.split("=");
  return (answers[key] || "") === expected;
}

export default function FormFill({
  fields,
  answers,
  onChange,
  uploadPath,
}: {
  fields: FillField[];
  answers: Record<string, string>;
  onChange: (key: string, value: string) => void;
  uploadPath?: string;
}) {
  const upload = async (key: string, file: File) => {
    if (!uploadPath) return;
    const body = new FormData();
    body.set("upload", file);
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API}${uploadPath}`, { method: "POST", body, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data as { detail?: string }).detail || "Upload failed");
    onChange(key, (data as { stored: string }).stored);
  };

  return (
    <div className="space-y-3">
      {fields.filter((field) => fieldVisible(field, answers)).map((field) => (
        <label key={field.key} className="block text-xs text-slate-500">
          {field.label}{field.required ? " *" : ""}
          {field.type === "long" ? (
            <textarea required={field.required} className="mt-1 w-full border rounded px-2 py-1 text-sm" rows={3} value={answers[field.key] || ""} onChange={(e) => onChange(field.key, e.target.value)} />
          ) : field.type === "choice" ? (
            <select required={field.required} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={answers[field.key] || ""} onChange={(e) => onChange(field.key, e.target.value)}>
              <option value="">Select</option>
              {field.options.map((option) => <option key={option}>{option}</option>)}
            </select>
          ) : field.type === "file" ? (
            <input className="mt-1 block text-sm" type="file" onChange={(e) => { const file = e.target.files?.[0]; if (file) upload(field.key, file).catch((error) => onChange(field.key, "")); }} />
          ) : (
            <input required={field.required && field.type !== "file"} type={field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "link" ? "url" : "text"} className="mt-1 w-full border rounded px-2 py-1 text-sm" value={answers[field.key] || ""} onChange={(e) => onChange(field.key, e.target.value)} />
          )}
          {field.type === "file" && answers[field.key] ? <span className="mt-1 block text-emerald-700">File kept</span> : null}
        </label>
      ))}
    </div>
  );
}
