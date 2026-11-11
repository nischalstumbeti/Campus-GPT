"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Person = {
  name: string;
  email: string;
  role: string;
  photo_url?: string;
  designation?: string;
  department?: string;
  school?: string;
  block?: string;
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || "U") + (parts[1]?.[0] || "")).toUpperCase();
}

export default function DirectoryPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [limited, setLimited] = useState(true);
  const [query, setQuery] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiFetch<{ limited: boolean; people: Person[] }>("/api/v1/directory")
      .then((data) => {
        setLimited(Boolean(data.limited));
        setPeople(data.people || []);
      })
      .catch((e) => setErr(e.message));
  }, []);

  const needle = query.trim().toLowerCase();
  const rows = people.filter((person) => {
    if (!needle) return true;
    return [person.name, person.email, person.role, person.designation, person.department, person.school, person.block]
      .join(" ")
      .toLowerCase()
      .includes(needle);
  });

  return (
    <AppShell>
      <section className="uis-panel">
        <h1 className="uis-panel-title">Directory</h1>
        <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">
            {limited
              ? "Official email addresses for faculty, the hostel warden, and administrators."
              : "Faculty, hostel warden, and administrators, with cabin details."}
          </p>
          <input
            className="border rounded px-2 py-1 text-sm"
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {err ? <p className="px-4 py-3 text-sm text-red-600">{err}</p> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="uis-table-head text-left">
              <tr>
                <th className="px-3 py-2">Photo</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Official</th>
                <th className="px-3 py-2">Email</th>
                {limited ? null : (
                  <>
                    <th className="px-3 py-2">Designation</th>
                    <th className="px-3 py-2">Department</th>
                    <th className="px-3 py-2">School</th>
                    <th className="px-3 py-2">Block</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((person) => (
                <tr key={person.email} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    {person.photo_url ? (
                      <img src={person.photo_url} alt="" className="h-12 w-10 object-cover border border-slate-300 bg-slate-100" />
                    ) : (
                      <div className="h-12 w-10 border border-slate-300 bg-slate-100 text-brand text-sm font-semibold flex items-center justify-center">
                        {initials(person.name)}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 font-medium">{person.name}</td>
                  <td className="px-3 py-2">{person.role}</td>
                  <td className="px-3 py-2">
                    <a className="text-[#0B2A4A] underline" href={`mailto:${person.email}`}>
                      {person.email}
                    </a>
                  </td>
                  {limited ? null : (
                    <>
                      <td className="px-3 py-2">{person.designation || "—"}</td>
                      <td className="px-3 py-2">{person.department || "—"}</td>
                      <td className="px-3 py-2">{person.school || "—"}</td>
                      <td className="px-3 py-2">{person.block || "—"}</td>
                    </>
                  )}
                </tr>
              ))}
              {!rows.length && !err ? (
                <tr>
                  <td colSpan={limited ? 4 : 8} className="px-3 py-4 text-slate-500">
                    No officials match this search.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
