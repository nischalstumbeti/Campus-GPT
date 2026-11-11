"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import UserEditor from "@/components/UserEditor";
import { apiDownload, apiFetch, apiUpload } from "@/lib/api";
import { confirmPhrase } from "@/lib/confirm";

type UserRow = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  department_code: string | null;
  is_active: boolean;
  has_photo?: boolean;
  created_at: string | null;
};

const ROLES: { value: string; label: string; privilege: string }[] = [
  { value: "faculty", label: "Faculty", privilege: "Own classes: attendance, marks, mentoring, and first-stage approvals." },
  { value: "hod", label: "Head of the Department", privilege: "Department classes and the second approval after the faculty advisor." },
  { value: "school_dean", label: "School Dean", privilege: "School classes, mentoring, and first-stage academic approvals." },
  { value: "director", label: "Director", privilege: "Campus overview: students, examinations, hall ticket, and directory." },
  { value: "operator", label: "Operator", privilege: "Create and update users, student records, and photos." },
  { value: "coe", label: "CoE / Principal", privilege: "Examinations, hall ticket, and application windows." },
  { value: "developer", label: "Developer", privilege: "Full system configuration, users, and settings." },
  { value: "admin", label: "Admin", privilege: "Users, students, examinations, and campus settings." },
  { value: "student", label: "Student", privilege: "Own dashboard, registration, and academic records." },
  { value: "staff", label: "Staff", privilege: "Campus staff directory and assigned office work." },
  { value: "hostel_admin", label: "Hostel warden", privilege: "Hostel students, attendance, and leave." },
];

type ImportResult = {
  created_count: number;
  error_count: number;
  message: string;
  created: { row: number; username: string; role: string }[];
  errors: { row: number; error: string }[];
};

export default function AdminUsersPage() {
  const [items, setItems] = useState<UserRow[]>([]);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [passwordFor, setPasswordFor] = useState<UserRow | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [password, setPassword] = useState("");
  const [passwordAgain, setPasswordAgain] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "campus123",
    role: "faculty",
    department_code: "CSE",
    school: "",
    year: 1,
    semester: 1,
    section: "A",
    batch: "2026",
    designation: "",
    abc_id: "",
    residence: "hostel",
    transport: "",
    residence_detail: "",
  });

  const load = async () => {
    const params = new URLSearchParams({ limit: "500" });
    if (q) params.set("q", q);
    if (roleFilter) params.set("role", roleFilter);
    const d = await apiFetch<{ items: UserRow[] }>(`/api/v1/admin/users?${params}`);
    setItems(d.items || []);
  };

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  const createUser = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const isStudent = form.role === "student";
      const userId = form.username.trim();
      const body: Record<string, unknown> = {
        username: userId,
        email: form.email,
        full_name: form.full_name,
        password: form.password,
        role: form.role,
        department_code: form.department_code || null,
        school: form.school,
        designation: form.designation,
        abc_id: form.abc_id,
        residence: form.residence,
        transport: form.residence === "day_scholar" ? form.transport : "",
        residence_detail: form.residence_detail,
      };
      if (isStudent) {
        body.student_id = userId;
        body.year = form.year;
        body.semester = form.semester;
        body.section = form.section;
        body.batch = form.batch;
      }
      if (form.role === "faculty" || form.role === "hod" || form.role === "school_dean") {
        body.faculty_id = userId;
      }
      const created = await apiFetch<{ id: number }>("/api/v1/admin/users", { method: "POST", body: JSON.stringify(body) });
      if (photo) await apiUpload(`/api/v1/admin/users/${created.id}/photo`, photo);
      setMsg(`Created ${ROLES.find((r) => r.value === form.role)?.label || form.role}: ${userId}`);
      setShowCreate(false);
      setPhoto(null);
      setForm((f) => ({ ...f, username: "", email: "", full_name: "", abc_id: "", residence_detail: "" }));
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = async () => {
    setBusy(true);
    setMsg("");
    try {
      await apiDownload("/api/v1/admin/users/import-template", "uis_users_import_template.csv");
      setMsg("Template downloaded — open in Excel, fill rows, then upload.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Template download failed");
    } finally {
      setBusy(false);
    }
  };

  const importFile = async (file: File) => {
    setBusy(true);
    setMsg("");
    setImportResult(null);
    try {
      const res = await apiUpload<ImportResult>("/api/v1/admin/users/import", file);
      setImportResult(res);
      setMsg(res.message);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeUser = async (u: UserRow) => {
    const ok = await confirmPhrase({
      title: `Delete ${u.username}`,
      detail: "This removes the account and the academic, fee, hostel, and message rows from the database.",
      phrase: u.username,
    });
    if (!ok) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await apiFetch<{ deleted: string; acknowledgement?: { number: string; email_sent: boolean } }>(
        `/api/v1/admin/users/${u.id}`,
        { method: "DELETE", body: JSON.stringify({ confirm: u.username }) }
      );
      const ack = res.acknowledgement;
      setMsg(
        `Deleted ${res.deleted} from the database.` +
          (ack ? ` Slip ${ack.number}. Email ${ack.email_sent ? "sent" : "not sent"}.` : "")
      );
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const openPassword = (u: UserRow) => {
    setPasswordFor(u);
    setPassword("");
    setPasswordAgain("");
    setMsg("");
  };

  const savePassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!passwordFor) return;
    if (password.length < 6) {
      setMsg("Password must be at least 6 characters.");
      return;
    }
    if (password !== passwordAgain) {
      setMsg("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/v1/admin/users/${passwordFor.id}`, {
        method: "PATCH",
        body: JSON.stringify({ password }),
      });
      setMsg(`Password updated for ${passwordFor.username}. They can use it on UIS and Campus-GPT login.`);
      setPasswordFor(null);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Password update failed");
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (u: UserRow) => {
    const next = !u.is_active;
    const ok = window.confirm(
      next ? `Enable ${u.username}? They will be able to sign in again.` : `Disable ${u.username}? They will not be able to sign in.`
    );
    if (!ok) return;
    setBusy(true);
    setMsg("");
    try {
      await apiFetch(`/api/v1/admin/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: next }),
      });
      setMsg(next ? `${u.username} is active again.` : `${u.username} is disabled.`);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not update the account");
    } finally {
      setBusy(false);
    }
  };

  const signInAs = async (u: UserRow) => {
    const password = window.prompt(`Enter your own administrator password to sign in as ${u.full_name}.`);
    if (!password) return;
    setBusy(true);
    setMsg("");
    try {
      const data = await apiFetch<{ access_token: string; role: string }>(`/api/v1/admin/users/${u.id}/impersonate`, {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      const current = localStorage.getItem("uis_token");
      if (current) localStorage.setItem("uis_admin_return", current);
      localStorage.setItem("uis_token", data.access_token);
      const role = (data.role || "").toLowerCase();
      const home =
        role === "student"
          ? "/student"
          : role === "faculty" || role === "hod" || role === "school_dean"
            ? "/faculty"
            : role === "hostel_admin" || role === "warden" || role === "hostel_warden"
              ? "/hostel"
              : "/admin";
      window.location.href = home;
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not sign in as that user");
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-[#0B2A4A]">Users</h1>
          <p className="text-sm text-slate-500">
            {items.length} account{items.length === 1 ? "" : "s"} in CIMS. Add students, faculty, hostel wardens and other roles one-by-one or via Excel/CSV.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setShowImport((v) => !v);
              setShowCreate(false);
            }}
            className="px-3 py-2 rounded-lg border border-[#0B2A4A] text-[#0B2A4A] text-sm font-medium"
          >
            {showImport ? "Close import" : "Import Excel / CSV"}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowCreate((v) => !v);
              setShowImport(false);
            }}
            className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm font-medium"
          >
            {showCreate ? "Close form" : "Add user manually"}
          </button>
        </div>
      </div>

      {msg && (
        <p className="text-sm mb-3 text-[#0B2A4A] bg-slate-100 border border-slate-200 rounded-lg px-3 py-2">{msg}</p>
      )}

      {showImport && (
        <section className="bg-white border rounded-xl p-4 mb-4 shadow-sm space-y-3">
          <h2 className="font-semibold text-[#0B2A4A]">Bulk import from Excel / CSV</h2>
          <ol className="text-sm text-slate-600 list-decimal pl-5 space-y-1">
            <li>Download the template (opens in Excel).</li>
            <li>
              Fill one row per person. Role can be: student, faculty, hod, hostel_admin (warden), exam_admin, admin,
              etc.
            </li>
            <li>Upload the saved .xlsx or .csv — accounts are created in UIS and can sign in to Campus-GPT with the same email.</li>
          </ol>
          <div className="flex flex-wrap gap-2 items-center">
            <button
              type="button"
              disabled={busy}
              onClick={downloadTemplate}
              className="px-3 py-2 rounded-lg bg-slate-100 text-sm font-medium disabled:opacity-50"
            >
              Download template
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="text-sm"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) importFile(f);
              }}
            />
          </div>
          {importResult && (
            <div className="text-sm border rounded-lg p-3 bg-slate-50 space-y-2">
              <p className="font-medium">
                Created {importResult.created_count} · Failed {importResult.error_count}
              </p>
              {!!importResult.created.length && (
                <p className="text-xs text-slate-600">
                  Added: {importResult.created.map((c) => `${c.username} (${c.role})`).join(", ")}
                </p>
              )}
              {!!importResult.errors.length && (
                <ul className="text-xs text-red-700 space-y-0.5 max-h-40 overflow-auto">
                  {importResult.errors.map((e) => (
                    <li key={`${e.row}-${e.error}`}>
                      Row {e.row}: {e.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      {showCreate && (
        <form onSubmit={createUser} className="bg-white border rounded-xl p-4 mb-4 shadow-sm grid sm:grid-cols-2 gap-3 text-sm">
          <h2 className="sm:col-span-2 font-semibold text-[#0B2A4A]">Add one account</h2>
          <label className="block">
            <span className="text-xs text-slate-500">Image</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              onChange={(e) => setPhoto(e.target.files?.[0] || null)}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Name</span>
            <input
              required
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Role</span>
            <select
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">{form.role === "student" ? "Register number" : "User ID"}</span>
            <input
              required
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Email</span>
            <input
              required
              type="email"
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Password</span>
            <input
              required
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">Department</span>
            <input
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.department_code}
              onChange={(e) => setForm({ ...form, department_code: e.target.value })}
              placeholder="CSE / ECE"
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">School</span>
            <input
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.school}
              onChange={(e) => setForm({ ...form, school: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-slate-500">ABC ID</span>
            <input
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.abc_id}
              onChange={(e) => setForm({ ...form, abc_id: e.target.value })}
            />
          </label>
          {form.role !== "student" && (
            <label className="block">
              <span className="text-xs text-slate-500">Designation</span>
              <input
                className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
            </label>
          )}
          {form.role === "student" && (
            <>
              <label className="block">
                <span className="text-xs text-slate-500">Batch</span>
                <input
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.batch}
                  onChange={(e) => setForm({ ...form, batch: e.target.value })}
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Year</span>
                <input
                  type="number"
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.year}
                  onChange={(e) => setForm({ ...form, year: Number(e.target.value) })}
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Section</span>
                <input
                  className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                  value={form.section}
                  onChange={(e) => setForm({ ...form, section: e.target.value })}
                />
              </label>
            </>
          )}
          <label className="block">
            <span className="text-xs text-slate-500">Stay</span>
            <select
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.residence}
              onChange={(e) => setForm({ ...form, residence: e.target.value, transport: "" })}
            >
              <option value="hostel">Hostel</option>
              <option value="day_scholar">Day scholar</option>
            </select>
          </label>
          {form.residence === "day_scholar" && (
            <label className="block">
              <span className="text-xs text-slate-500">Day scholar travel</span>
              <select
                className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
                value={form.transport}
                onChange={(e) => setForm({ ...form, transport: e.target.value })}
              >
                <option value="">Own arrangement</option>
                <option value="institute_bus">Institute Bus</option>
              </select>
            </label>
          )}
          <label className="block sm:col-span-2">
            <span className="text-xs text-slate-500">
              {form.residence === "hostel"
                ? "Room detail"
                : form.transport === "institute_bus"
                  ? "Bus detail"
                  : "Remarks"}
            </span>
            <input
              className="w-full border rounded-lg px-2 py-1.5 mt-0.5"
              value={form.residence_detail}
              onChange={(e) => setForm({ ...form, residence_detail: e.target.value })}
            />
          </label>
          <div className="sm:col-span-2">
            <button type="submit" disabled={busy} className="px-4 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm disabled:opacity-50">
              Create account
            </button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-xl p-4 mb-4 shadow-sm">
        <h2 className="text-sm font-semibold text-[#0B2A4A] mb-2">Roles and privilege</h2>
        <ul className="text-sm space-y-1">
          {ROLES.filter((r) => r.value !== "student").map((r) => (
            <li key={r.value}>
              <span className="font-medium">{r.label}.</span> {r.privilege}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <input
          className="border rounded-lg px-3 py-2 text-sm"
          placeholder="Search username / name / email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="border rounded-lg px-3 py-2 text-sm" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="">All roles</option>
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button type="button" className="px-3 py-2 rounded-lg border text-sm" onClick={() => load()}>
          Search
        </button>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F6F9] text-xs text-slate-500 text-left">
            <tr>
              <th className="px-3 py-2">Photo</th>
              <th className="px-3 py-2">Username</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Dept</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id} className="border-t">
                <td className="px-3 py-2 text-xs text-slate-500">{u.has_photo ? "Added" : "None"}</td>
                <td className="px-3 py-2 font-medium">{u.username}</td>
                <td className="px-3 py-2">
                  <p>{u.full_name}</p>
                  <p className="text-xs text-slate-400">{u.email}</p>
                </td>
                <td className="px-3 py-2 capitalize">{u.role.replace(/_/g, " ")}</td>
                <td className="px-3 py-2">{u.department_code || "—"}</td>
                <td className="px-3 py-2">{u.is_active ? "Active" : "Inactive"}</td>
                <td className="px-3 py-2 text-xs">{u.created_at ? u.created_at.slice(0, 10) : "—"}</td>
                <td className="px-3 py-2 whitespace-nowrap space-x-3">
                  <button type="button" disabled={busy} className="text-xs font-semibold text-[#0B2A4A]" onClick={() => setEditingId(u.id)}>
                    Edit
                  </button>
                  <button type="button" disabled={busy} className="text-xs font-semibold text-[#0B2A4A]" onClick={() => signInAs(u)}>
                    Sign in as
                  </button>
                  <button type="button" disabled={busy} className="text-xs font-semibold text-[#0B2A4A]" onClick={() => openPassword(u)}>
                    Reset password
                  </button>
                  <button type="button" disabled={busy} className="text-xs font-semibold text-amber-800" onClick={() => toggleActive(u)}>
                    {u.is_active ? "Disable" : "Enable"}
                  </button>
                  <button type="button" disabled={busy} className="text-xs font-semibold text-rose-700" onClick={() => removeUser(u)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editingId !== null && (
        <UserEditor
          userId={editingId}
          roles={ROLES}
          busy={busy}
          onClose={() => setEditingId(null)}
          onSaved={(message) => {
            setMsg(message);
            setEditingId(null);
            void load();
          }}
          onError={(message) => setMsg(message)}
        />
      )}

      {passwordFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-labelledby="reset-password-title">
          <form onSubmit={savePassword} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl space-y-3">
            <h2 id="reset-password-title" className="text-lg font-bold text-[#0B2A4A]">
              Reset password
            </h2>
            <p className="text-sm text-slate-500">
              New password for <span className="font-semibold text-slate-800">{passwordFor.full_name}</span> ({passwordFor.username}). Minimum 6 characters.
            </p>
            <label className="block text-sm">
              <span className="text-slate-600">New password</span>
              <input
                type="password"
                autoFocus
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-600">Confirm password</span>
              <input
                type="password"
                required
                minLength={6}
                value={passwordAgain}
                onChange={(e) => setPasswordAgain(e.target.value)}
                className="mt-1 w-full rounded-lg border px-3 py-2"
              />
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" className="px-3 py-2 rounded-lg border text-sm" onClick={() => setPasswordFor(null)} disabled={busy}>
                Cancel
              </button>
              <button type="submit" className="px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm" disabled={busy}>
                Save password
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
