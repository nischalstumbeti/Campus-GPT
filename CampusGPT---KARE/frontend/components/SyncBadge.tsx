"use client";

export default function SyncBadge({ source }: { source?: string | null }) {
  const raw = (source || "").trim();
  const s = raw.toUpperCase();
  const synced = s === "UIS" || s === "KARE_UIS" || s === "KARE UIS";
  const unknown = !raw;
  const label = synced ? "Synced with UIS" : unknown ? "Source unknown" : "Local copy";
  const title = synced
    ? "Live data from KARE UIS"
    : unknown
      ? "Response did not report a sync source"
      : "Stored locally (not confirmed from UIS)";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        synced
          ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
          : "bg-slate-100 text-slate-600 border border-slate-200"
      }`}
      title={title}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${synced ? "bg-emerald-500" : "bg-slate-400"}`} />
      {label}
    </span>
  );
}
