"use client";

type Slip = {
  student_id: string;
  name: string;
  programme: string;
  section: string;
  semester: number;
  batch: string;
  kind: string;
  issued_on: string;
  courses: { code: string; name: string }[];
};

const TITLES: Record<string, string> = {
  registration: "Course Registration",
  withdrawal: "Course Withdrawal",
  revaluation: "Revaluation",
  arrear: "Arrear",
  backlog: "Backlog",
};

export default function AckSlip({ slip, onClose }: { slip: Slip; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-start justify-center p-4 overflow-auto" onClick={onClose}>
      <article className="bg-white w-full max-w-2xl shadow-lg my-8" onClick={(event) => event.stopPropagation()}>
        <header className="uis-panel-title flex items-center justify-between gap-3">
          <span>Acknowledgement slip</span>
          <button type="button" className="text-white text-sm underline" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="px-6 py-5 text-sm">
          <h2 className="text-lg font-semibold text-brand">{TITLES[slip.kind] || slip.kind}</h2>
          <p className="mt-1 text-slate-600">Approved by the faculty advisor and the Head of Department.</p>
          <table className="w-full mt-4">
            <tbody>
              <tr className="border-b border-slate-200">
                <th className="py-2 text-left text-slate-600 w-40">Register number</th>
                <td>{slip.student_id}</td>
              </tr>
              <tr className="border-b border-slate-200">
                <th className="py-2 text-left text-slate-600">Name</th>
                <td>{slip.name}</td>
              </tr>
              <tr className="border-b border-slate-200">
                <th className="py-2 text-left text-slate-600">Programme</th>
                <td>{slip.programme}</td>
              </tr>
              <tr className="border-b border-slate-200">
                <th className="py-2 text-left text-slate-600">Section / Semester</th>
                <td>
                  {slip.section} · Semester {slip.semester}
                </td>
              </tr>
              <tr className="border-b border-slate-200">
                <th className="py-2 text-left text-slate-600">Issued</th>
                <td>{slip.issued_on}</td>
              </tr>
            </tbody>
          </table>
          <h3 className="mt-4 font-semibold text-brand">Courses</h3>
          <ul className="mt-2 space-y-1">
            {slip.courses.map((course) => (
              <li key={course.code}>
                {course.code} · {course.name}
              </li>
            ))}
          </ul>
          <div className="mt-6 flex gap-2 print:hidden">
            <button type="button" className="px-3 py-1.5 rounded bg-brand text-white" onClick={() => window.print()}>
              Print slip
            </button>
          </div>
        </div>
      </article>
    </div>
  );
}
