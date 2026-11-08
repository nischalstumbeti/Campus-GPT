"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch, apiUpload } from "@/lib/api";

type RoleOption = { value: string; label: string };

export type EditableUser = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  department_code: string | null;
  designation: string;
  school: string;
  office: string;
  cabin_block: string;
  abc_id: string;
  residence: string;
  transport: string;
  residence_detail: string;
  is_active: boolean;
  photo_url: string;
  student_id: string;
  year: number | null;
  semester: number | null;
  section: string;
  batch: string;
};

type Props = {
  userId: number;
  roles: RoleOption[];
  busy: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
};

export default function UserEditor({ userId, roles, busy, onClose, onSaved, onError }: Props) {
  const [detail, setDetail] = useState<EditableUser | null>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiFetch<EditableUser>(`/api/v1/admin/users/${userId}`)
      .then((row) => {
        if (cancelled) return;
        setDetail(row);
        setPreview(row.photo_url || "");
      })
      .catch((err) => onError(err instanceof Error ? err.message : "Could not load this user"));
    return () => {
      cancelled = true;
    };
    // onError is a fresh function from the page; userId is the load key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  useEffect(() => {
    if (!photoFile) return;
    const url = URL.createObjectURL(photoFile);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    const body: Record<string, unknown> = {
      email: detail.email.trim(),
      full_name: detail.full_name.trim(),
      role: detail.role,
      department_code: detail.department_code || null,
      designation: detail.designation,
      school: detail.school,
      office: detail.office,
      cabin_block: detail.cabin_block,
      abc_id: detail.abc_id,
      residence: detail.residence,
      transport: detail.transport,
      residence_detail: detail.residence_detail,
    };
    if (detail.student_id) {
      body.student_id = detail.student_id.trim();
      body.year = detail.year;
      body.semester = detail.semester;
      body.section = detail.section;
      body.batch = detail.batch;
    }
    try {
      await apiFetch(`/api/v1/admin/users/${detail.id}`, { method: "PATCH", body: JSON.stringify(body) });
      if (photoFile) {
        const uploaded = await apiUpload<{ photo_url: string }>(`/api/v1/admin/users/${detail.id}/photo`, photoFile);
        setPreview(uploaded.photo_url || preview);
        setPhotoFile(null);
      }
      onSaved(`Saved details for ${detail.username}.`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not save this user");
    }
  };

  const removePhoto = async () => {
    if (!detail) return;
    try {
      await apiFetch(`/api/v1/admin/users/${detail.id}/photo`, { method: "DELETE" });
      setPreview("");
      setPhotoFile(null);
      setDetail({ ...detail, photo_url: "" });
      onSaved(`Removed the photo for ${detail.username}.`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not remove the photo");
    }
  };

  const set = (patch: Partial<EditableUser>) => setDetail((row) => (row ? { ...row, ...patch } : row));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-labelledby="edit-user-title">
      <form onSubmit={save} className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white p-5 shadow-xl space-y-3">
        <h2 id="edit-user-title" className="text-lg font-bold text-[#0B2A4A]">
          Edit user
        </h2>
        {!detail ? (
          <p className="text-sm text-slate-500">Loading account…</p>
        ) : (
          <>
            <p className="text-sm text-slate-500">
              {detail.full_name} ({detail.username}). The same photo is used on the student page, hall ticket, hostel, and directory.
            </p>
            <div className="flex items-center gap-3">
              {preview ? (
                <img src={preview} alt="" className="h-20 w-16 object-cover border border-slate-300 bg-slate-100" />
              ) : (
                <div className="h-20 w-16 border border-slate-300 bg-slate-100" />
              )}
              <div className="text-sm space-y-2">
                <label className="block">
                  <span className="text-slate-600">Photo (JPG, PNG, or WebP, max 1.5 MB)</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="mt-1 block text-sm"
                    onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
                  />
                </label>
                {preview ? (
                  <button type="button" className="text-xs font-semibold text-rose-700" onClick={removePhoto} disabled={busy}>
                    Remove photo
                  </button>
                ) : null}
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="text-sm">
                <span className="text-slate-600">Full name</span>
                <input required value={detail.full_name} onChange={(e) => set({ full_name: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Email</span>
                <input required type="email" value={detail.email} onChange={(e) => set({ email: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Role</span>
                <select value={detail.role} onChange={(e) => set({ role: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2">
                  {!roles.some((r) => r.value === detail.role) ? <option value={detail.role}>{detail.role}</option> : null}
                  {roles.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Department</span>
                <input value={detail.department_code || ""} onChange={(e) => set({ department_code: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Designation</span>
                <input value={detail.designation} onChange={(e) => set({ designation: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">School</span>
                <input value={detail.school} onChange={(e) => set({ school: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Office</span>
                <input value={detail.office} onChange={(e) => set({ office: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
              <label className="text-sm">
                <span className="text-slate-600">Block / cabin</span>
                <input value={detail.cabin_block} onChange={(e) => set({ cabin_block: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
              </label>
            </div>
            {detail.student_id ? (
              <div className="grid sm:grid-cols-2 gap-3 border-t pt-3">
                <label className="text-sm">
                  <span className="text-slate-600">Register number</span>
                  <input required value={detail.student_id} onChange={(e) => set({ student_id: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
                <label className="text-sm">
                  <span className="text-slate-600">Batch</span>
                  <input value={detail.batch} onChange={(e) => set({ batch: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
                <label className="text-sm">
                  <span className="text-slate-600">Year</span>
                  <input type="number" min={1} value={detail.year ?? 1} onChange={(e) => set({ year: Number(e.target.value) })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
                <label className="text-sm">
                  <span className="text-slate-600">Semester</span>
                  <input type="number" min={1} value={detail.semester ?? 1} onChange={(e) => set({ semester: Number(e.target.value) })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
                <label className="text-sm">
                  <span className="text-slate-600">Section</span>
                  <input value={detail.section} onChange={(e) => set({ section: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
                <label className="text-sm">
                  <span className="text-slate-600">ABC id</span>
                  <input value={detail.abc_id} onChange={(e) => set({ abc_id: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" />
                </label>
              </div>
            ) : null}
          </>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="px-3 py-2 rounded-lg border text-sm" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button type="submit" className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm" disabled={busy || !detail}>
            Save details
          </button>
        </div>
      </form>
    </div>
  );
}
