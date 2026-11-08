"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Upload, FileStack, CheckCircle, XCircle } from "lucide-react";
import CloudBackground from "@/components/CloudBackground";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";
const ALLOWED = ".pdf,.docx,.pptx,.txt,.md,.csv";
const ALLOWED_LIST = ["PDF", "DOCX", "PPTX", "TXT", "MD", "CSV"];

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [results, setResults] = useState<{ name: string; chunks: number; ok: boolean; detail?: string }[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    const valid = selected.filter((f) => {
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      return ALLOWED_LIST.some((x) => ext === "." + x.toLowerCase());
    });
    if (valid.length > 0) {
      setFiles(valid);
      setStatus("idle");
      setMessage("");
      setResults([]);
    } else if (selected.length > 0) {
      setMessage(`Allowed: ${ALLOWED_LIST.join(", ")}`);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setStatus("uploading");
    setMessage("");
    setResults([]);

    const outcomes: { name: string; chunks: number; ok: boolean; detail?: string }[] = [];

    const token = typeof window !== "undefined" ? localStorage.getItem("campus_gpt_token") : null;

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        // Prefer authenticated admin upload; fall back to public ingest (local embeddings OK)
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        let res = await fetch(`${API_BASE}/api/upload`, {
          method: "POST",
          headers,
          body: formData,
        });
        if (res.status === 401 || res.status === 403) {
          res = await fetch(`${API_BASE}/api/upload/public`, {
            method: "POST",
            body: formData,
          });
        }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = data.detail;
          throw new Error(typeof detail === "string" ? detail : "Upload failed");
        }
        const ok = data.status === "completed" && (data.chunks ?? 0) > 0;
        outcomes.push({
          name: file.name,
          chunks: data.chunks ?? 0,
          ok,
          detail: ok ? undefined : data.reason || data.message || data.status,
        });
      } catch (e) {
        outcomes.push({
          name: file.name,
          chunks: 0,
          ok: false,
          detail: e instanceof Error ? e.message : "Upload failed",
        });
      }
    }

    setResults(outcomes);
    const okCount = outcomes.filter((o) => o.ok).length;
    const totalChunks = outcomes.reduce((s, o) => s + o.chunks, 0);
    setStatus(okCount > 0 ? "success" : "error");
    setMessage(
      okCount === files.length
        ? `All ${files.length} file(s) ingested. ${totalChunks} chunks added to knowledge base.`
        : `${okCount}/${files.length} succeeded. ${totalChunks} chunks added.`
    );
    setFiles([]);
  };

  return (
    <div className="min-h-screen bg-[#FFFFFF] font-sans relative overflow-hidden">
      <CloudBackground variant="admin" />
      <div className="max-w-2xl mx-auto px-6 py-8 relative z-10">
        <Link
          href="/admin"
          className="flex items-center gap-2 text-gray-600 hover:text-primary transition-colors mb-8"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Admin
        </Link>

        <div className="rounded-2xl bg-white border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
            <Image src="/kare-logo.png" alt="KARE" width={32} height={32} className="object-contain" />
            <Upload className="w-5 h-5 text-primary" />
            <h1 className="font-semibold text-xl text-primary">Knowledge Base Upload</h1>
          </div>
          <div className="p-6">
            <p className="text-gray-600 text-sm mb-2">
              Add policies, circulars, rules, brochures, and other KARE documents to the knowledge base.
              Campus-GPT will use them to answer questions precisely.
            </p>
            <p className="text-gray-500 text-xs mb-6">
              Supported: {ALLOWED_LIST.join(", ")}
            </p>

            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                files.length > 0 ? "border-primary bg-primary/5" : "border-gray-200 hover:border-primary/50"
              }`}
            >
              <input
                type="file"
                accept={ALLOWED}
                multiple
                onChange={handleFileChange}
                className="hidden"
                id="file-input"
              />
              <label
                htmlFor="file-input"
                className="cursor-pointer flex flex-col items-center gap-3"
              >
                <FileStack className="w-12 h-12 text-gray-400" />
                <span className="text-sm text-gray-600">
                  {files.length > 0
                    ? `${files.length} file(s) selected`
                    : "Click to select or drag files"}
                </span>
                {files.length > 0 && (
                  <ul className="text-xs text-gray-500 text-left w-full max-h-24 overflow-y-auto">
                    {files.map((f) => (
                      <li key={f.name} className="truncate">
                        {f.name}
                      </li>
                    ))}
                  </ul>
                )}
              </label>
            </div>

            {files.length > 0 && (
              <button
                onClick={handleUpload}
                disabled={status === "uploading"}
                className="mt-6 w-full py-3 rounded-xl bg-primary text-white font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {status === "uploading" ? "Processing..." : `Upload & Ingest ${files.length} file(s)`}
              </button>
            )}

            {results.length > 0 && (
              <div className="mt-4 space-y-2">
                {results.map((r) => (
                  <div
                    key={r.name}
                    className={`flex items-center gap-2 p-2 rounded-lg text-sm ${
                      r.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                    }`}
                  >
                    {r.ok ? (
                      <CheckCircle className="w-4 h-4 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 flex-shrink-0" />
                    )}
                    <span className="truncate flex-1">
                      {r.name}
                      {!r.ok && r.detail ? ` — ${r.detail}` : ""}
                    </span>
                    {r.ok && <span>{r.chunks} chunks</span>}
                  </div>
                ))}
              </div>
            )}

            {message && (
              <div
                className={`mt-4 flex items-center gap-2 p-4 rounded-lg ${
                  status === "success" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                }`}
              >
                {status === "success" ? (
                  <CheckCircle className="w-5 h-5 flex-shrink-0" />
                ) : (
                  <XCircle className="w-5 h-5 flex-shrink-0" />
                )}
                <span className="text-sm">{message}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
