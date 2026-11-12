"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Route = { id: number; name: string; steps: string[]; active: boolean };
type Letter = { id: number; subject: string; body: string; name: string; step: string; status: string };

const OFFICES: { role: string; label: string; roles: string[] }[] = [
  { role: "advisor", label: "Advisor", roles: ["faculty", "hod"] },
  { role: "hod", label: "HoD", roles: ["hod"] },
  { role: "school_dean", label: "School dean", roles: ["school_dean", "faculty"] },
  { role: "director", label: "Director", roles: ["director", "university_admin"] },
  { role: "coe", label: "COE", roles: ["coe", "university_admin"] },
  { role: "admin", label: "Admin", roles: ["university_admin", "admin", "super_admin", "operator", "developer"] },
];

type Person = { id: number; name: string; department: string; role: string };

type Chosen = { role: string; userId: number; label: string };

export default function AdminRequestsPage() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [inbox, setInbox] = useState<Letter[]>([]);
  const [directory, setDirectory] = useState<Person[]>([]);
  const [chosen, setChosen] = useState<Chosen[]>([]);
  const [officeRole, setOfficeRole] = useState("advisor");
  const [personId, setPersonId] = useState("");
  const [name, setName] = useState("Bonafide");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    apiFetch<{ items: Route[] }>("/api/v1/admin/request-routes")
      .then((data) => setRoutes(data.items || []))
      .catch(() => setRoutes([]));
    apiFetch<{ items: Letter[] }>("/api/v1/requests/inbox").then((data) => setInbox(data.items || [])).catch(() => setInbox([]));
    const roles = Array.from(new Set(OFFICES.flatMap((office) => office.roles)));
    Promise.all(
      roles.map((role) =>
        apiFetch<{ items: { id: number; full_name?: string; username?: string; department_code?: string; role?: string }[] }>(
          `/api/v1/admin/users?role=${role}&limit=200`
        )
          .then((data) => data.items || [])
          .catch(() => [])
      )
    ).then((groups) => {
      const seen = new Set<number>();
      const people: Person[] = [];
      groups.flat().forEach((item) => {
        if (seen.has(item.id)) return;
        seen.add(item.id);
        people.push({
          id: item.id,
          name: item.full_name || item.username || "User",
          department: item.department_code || "",
          role: item.role || "",
        });
      });
      setDirectory(people);
      if (!people.length) setErr("No faculty, HoD, or admin accounts were found in Users.");
    });
  };

  useEffect(() => { load(); }, []);

  const office = OFFICES.find((item) => item.role === officeRole) || OFFICES[0];
  const people = directory.filter((person) => office.roles.includes(person.role));

  const addOffice = () => {
    const person = people.find((item) => item.id === Number(personId));
    if (!person) {
      setErr(people.length ? "Select the person for that office." : `No ${office.label} account is in Users yet.`);
      return;
    }
    if (chosen.some((item) => item.role === office.role)) {
      setErr("That office is already on this route.");
      return;
    }
    setErr("");
    setChosen((current) => [...current, { role: office.role, userId: person.id, label: `${office.label} · ${person.name}` }]);
    setPersonId("");
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setErr("");
    if (!chosen.length) {
      setErr("Add the advisor, HoD, or school dean from the list.");
      return;
    }
    try {
      await apiFetch("/api/v1/admin/request-routes", {
        method: "POST",
        body: JSON.stringify({ name, steps: chosen.map((item) => `${item.role}:${item.userId}`).join(","), active: true }),
      });
      setMsg("Route saved. Students can choose it when they write a letter.");
      setChosen([]);
      load();
    } catch (error) {
      const text = error instanceof Error ? error.message : "Could not save the route";
      setErr(text === "Not Found" ? "The route could not be saved because the university API is still on the previous build. The people list is ready; save again after that API restarts." : text);
    }
  };

  const decide = async (id: number, decision: string) => {
    await apiFetch(`/api/v1/requests/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, note: "" }) });
    setMsg(decision === "approve" ? "Passed to the next office." : "Letter returned.");
    load();
  };

  return (
    <AppShell>
      <section className="uis-panel mb-4">
        <h1 className="uis-panel-title">Request routes</h1>
        <p className="px-4 pt-3 text-sm text-slate-600">A student letter moves through these offices in order. Pick the advisor, HoD, and school dean from the directory. Do not type the names.</p>
        <form onSubmit={save} className="p-4 space-y-3">
          {err ? <p className="text-sm text-red-600">{err}</p> : null}
          {msg ? <p className="text-sm text-emerald-700">{msg}</p> : null}
          <label className="block text-xs text-slate-500">Name
            <input required className="mt-1 w-full border rounded px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <div className="grid md:grid-cols-3 gap-2 items-end">
            <label className="text-xs text-slate-500">Office
              <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={officeRole} onChange={(e) => { setOfficeRole(e.target.value); setPersonId(""); }}>
                {OFFICES.map((item) => <option key={item.role} value={item.role}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-500">Person
              <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={personId} onChange={(e) => setPersonId(e.target.value)}>
                <option value="">{people.length ? "Select" : "No account for this office"}</option>
                {people.map((person) => <option key={person.id} value={person.id}>{person.name}{person.department ? ` · ${person.department}` : ""}</option>)}
              </select>
            </label>
            <button type="button" className="px-3 py-1.5 rounded border text-sm" onClick={addOffice}>Add office</button>
          </div>
          <ol className="text-sm list-decimal pl-5">
            {chosen.map((item, index) => (
              <li key={item.role} className="py-1">
                {item.label}
                <button type="button" className="ml-2 text-xs underline" onClick={() => setChosen((current) => current.filter((_, at) => at !== index))}>Remove</button>
              </li>
            ))}
            {!chosen.length ? <li className="list-none -ml-5 text-slate-500">No offices added yet.</li> : null}
          </ol>
          <button className="px-3 py-1.5 rounded bg-[#0B2A4A] text-white text-sm">Save route</button>
        </form>
        <ul className="px-4 pb-4 text-sm">
          {routes.map((route) => <li key={route.id} className="border-t py-2">{route.name}: {route.steps.join(" → ")}{route.active ? "" : " (closed)"}</li>)}
        </ul>
      </section>
      <section className="uis-panel">
        <h2 className="uis-panel-title">Waiting at your desk</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500"><tr><th className="px-3 py-2">From</th><th>Subject</th><th></th></tr></thead>
          <tbody>
            {inbox.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-3 py-2">{item.name}</td>
                <td className="px-3 py-2">{item.subject}<div className="text-xs text-slate-500">{item.body}</div></td>
                <td className="px-3 py-2 space-x-2">
                  <button type="button" className="underline" onClick={() => decide(item.id, "approve")}>Approve</button>
                  <button type="button" className="underline" onClick={() => decide(item.id, "reject")}>Return</button>
                </td>
              </tr>
            ))}
            {!inbox.length ? <tr><td colSpan={3} className="px-3 py-4 text-slate-500">Nothing is waiting for this login.</td></tr> : null}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
