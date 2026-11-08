"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Sparkles } from "lucide-react";
import CloudBackground from "@/components/CloudBackground";
import { apiFetch, INTERNET_ISSUE_MESSAGE } from "@/lib/network";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

const COURSES = [
  "",
  "Bachelor of Technology",
  "Master of Technology",
  "Bachelor of Science",
  "Master of Science",
  "Bachelor of Arts",
  "Master of Arts",
  "Master of Business Administration",
  "Bachelor of Business Administration",
  "Bachelor of Commerce",
  "Master of Commerce",
  "Bachelor of Computer Applications",
  "Master of Computer Applications",
  "Doctor of Philosophy",
  "Other",
];
const SUBJECTS = ["", "CSE", "ECE", "EEE", "Mechanical", "Civil", "IT", "Data Science", "AI/ML", "Business", "Commerce", "Other"];
const PROGRAM_LEVELS = ["", "UG (Undergraduate)", "PG (Postgraduate)", "PhD"];

export default function RecommendPage() {
  const [course, setCourse] = useState("");
  const [subject, setSubject] = useState("");
  const [budget, setBudget] = useState("");
  const [marks, setMarks] = useState("");
  const [board, setBoard] = useState("");
  const [state, setState] = useState("");
  const [programLevel, setProgramLevel] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const res = await apiFetch(`${API_BASE}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          course: course || null,
          subject: subject || null,
          budget: budget || null,
          marks: marks ? parseFloat(marks) : null,
          board: board || null,
          state: state || null,
          program_level: programLevel || null,
        }),
      });
      const data = await res.json();
      setResult(data.recommendations || "No recommendations generated.");
    } catch (e) {
      setResult(INTERNET_ISSUE_MESSAGE);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FFFFFF] font-sans relative overflow-hidden">
      <CloudBackground variant="form" />
      <div className="max-w-2xl mx-auto px-6 py-8 relative z-10">
        <Link
          href="/"
          className="flex items-center gap-2 text-gray-600 hover:text-primary transition-colors mb-8"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>

        <div className="rounded-2xl bg-white border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
            <Image src="/kare-logo.png" alt="KARE" width={32} height={32} className="object-contain" />
            <Sparkles className="w-5 h-5 text-primary" />
            <h1 className="font-semibold text-xl text-primary">Course & College Recommendations</h1>
          </div>
          <div className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Program Level</label>
                <select
                  value={programLevel}
                  onChange={(e) => setProgramLevel(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30 bg-white"
                >
                  {PROGRAM_LEVELS.map((opt) => (
                    <option key={opt || "empty"} value={opt}>
                      {opt || "Select UG / PG / PhD"}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Course</label>
                <select
                  value={course}
                  onChange={(e) => setCourse(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30 bg-white"
                >
                  {COURSES.map((opt) => (
                    <option key={opt || "empty"} value={opt}>
                      {opt || "Select course"}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject / Stream</label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30 bg-white"
                >
                  {SUBJECTS.map((opt) => (
                    <option key={opt || "empty"} value={opt}>
                      {opt || "Select subject"}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Marks Obtained (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={marks}
                  onChange={(e) => setMarks(e.target.value)}
                  placeholder="e.g. 85"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Board</label>
                <input
                  type="text"
                  value={board}
                  onChange={(e) => setBoard(e.target.value)}
                  placeholder="e.g. CBSE, State Board"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">State</label>
                <input
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  placeholder="e.g. Tamil Nadu, Karnataka"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Budget (optional)</label>
                <input
                  type="text"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="e.g. 2 Lakhs per year"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-xl bg-primary text-white font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {loading ? "Generating..." : "Get Recommendations"}
              </button>
            </form>

            {result && (
              <div className="mt-6 p-6 rounded-xl bg-primary/5 border border-primary/20">
                <h3 className="font-semibold text-primary mb-3">Recommendations</h3>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{result}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
