"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type Profile = {
  student_id: string;
  name: string;
  programme: string;
  batch: string;
  section: string;
  year: number;
  semester: number;
  photo_url: string;
  hostel: string;
  block: string;
  room: string;
  bed: string;
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || "S") + (parts[1]?.[0] || "")).toUpperCase();
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <tr className="border-b border-slate-200 last:border-0">
      <th className="w-[46%] px-3 py-2 text-left text-sm font-medium text-slate-600 bg-slate-50">{label}</th>
      <td className="px-3 py-2 text-sm text-slate-800">{value === "" || value === null || value === undefined ? "—" : value}</td>
    </tr>
  );
}

export default function HostelStudentPage() {
  const params = useParams();
  const studentId = String(params.studentId || "");
  const [data, setData] = useState<Profile | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!studentId) return;
    apiFetch<Profile>(`/api/v1/hostel/students/${studentId}`)
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [studentId]);

  return (
    <AppShell>
      <Link href="/hostel/leaves" className="text-sm text-[#0B2A4A] underline">
        ← Leave approvals
      </Link>
      {err ? <p className="mt-3 text-sm text-red-600">{err}</p> : null}
      {data ? (
        <div className="mt-3 space-y-4">
          <section className="uis-panel">
            <h1 className="uis-panel-title">Personal Details</h1>
            <div className="grid lg:grid-cols-[150px_1fr_1fr]">
              <div className="p-4 border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col items-center">
                {data.photo_url ? (
                  <img src={data.photo_url} alt={`${data.name} photo`} className="h-40 w-32 object-cover border border-slate-300 bg-slate-100" />
                ) : (
                  <div className="h-40 w-32 border border-slate-300 bg-slate-100 text-brand flex items-center justify-center text-3xl font-semibold">
                    {initials(data.name)}
                  </div>
                )}
              </div>
              <table className="w-full border-b lg:border-b-0 lg:border-r border-slate-200">
                <tbody>
                  <Row label="Register Number" value={data.student_id} />
                  <Row label="Name of the Student" value={data.name} />
                  <Row label="Degree / Programme" value={data.programme} />
                  <Row label="Batch" value={data.batch} />
                  <Row label="Section" value={data.section} />
                </tbody>
              </table>
              <table className="w-full">
                <tbody>
                  <Row label="Year" value={data.year} />
                  <Row label="Semester" value={data.semester} />
                </tbody>
              </table>
            </div>
          </section>
          <section className="uis-panel">
            <h2 className="uis-panel-title">Hostel room</h2>
            <table className="w-full">
              <tbody>
                <Row label="Hostel" value={data.hostel} />
                <Row label="Block" value={data.block} />
                <Row label="Room" value={data.room} />
                <Row label="Bed" value={data.bed} />
              </tbody>
            </table>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
