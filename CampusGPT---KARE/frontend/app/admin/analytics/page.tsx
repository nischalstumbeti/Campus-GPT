"use client";

import { useState, useEffect } from "react";
import { BarChart3, TrendingUp, Users, Award, Target } from "lucide-react";
import CopilotShell from "@/components/CopilotShell";
import RequireAuth from "@/components/RequireAuth";
import { apiGet } from "@/lib/api";

type AnalyticsData = {
  total_queries: number;
  failed_count: number;
  top_queries: { query: string; count: number }[];
  common_concerns?: Record<string, number>;
  leaderboard?: { name: string; email: string; points: number }[];
};

function AnalyticsInner() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<AnalyticsData>("/api/analytics/public")
      .then((d) => {
        if (cancelled) return;
        setData({
          total_queries: Number(d.total_queries) || 0,
          failed_count: Number(d.failed_count) || 0,
          top_queries: Array.isArray(d.top_queries) ? d.top_queries : [],
          common_concerns: d.common_concerns || {},
          leaderboard: Array.isArray(d.leaderboard) ? d.leaderboard : [],
        });
        setError(null);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message || "Failed to load analytics");
        setData({
          total_queries: 0,
          failed_count: 0,
          top_queries: [],
          common_concerns: {},
          leaderboard: [],
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <CopilotShell title="Analytics">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-primary">Analytics</h1>
          <p className="text-sm text-gray-600 mt-1">
            Chat usage, common concerns, and query volume across Campus-GPT.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error}
          </div>
        )}

        {!data ? (
          <p className="text-gray-500">Loading analytics...</p>
        ) : (
          <div className="space-y-8">
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-5 rounded-2xl bg-white border border-gray-100 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <BarChart3 className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Total Queries</p>
                  <p className="text-2xl font-bold text-primary">{data.total_queries}</p>
                </div>
              </div>
              <div className="p-5 rounded-2xl bg-white border border-gray-100 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Failed / Escalated</p>
                  <p className="text-2xl font-bold text-amber-600">{data.failed_count}</p>
                </div>
              </div>
              <div className="p-5 rounded-2xl bg-white border border-gray-100 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <span className="text-xl font-bold text-primary">
                    {data.total_queries
                      ? ((data.failed_count / data.total_queries) * 100).toFixed(1)
                      : "0.0"}
                    %
                  </span>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Failure Rate</p>
                </div>
              </div>
            </div>

            {data.common_concerns && Object.keys(data.common_concerns).length > 0 && (
              <div className="rounded-2xl bg-white border border-gray-100 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                  <Target className="w-5 h-5 text-primary" />
                  <h2 className="font-semibold text-primary">Common Concerns</h2>
                </div>
                <div className="p-5 flex flex-wrap gap-2">
                  {Object.entries(data.common_concerns).map(([cat, count]) => (
                    <span
                      key={cat}
                      className="px-3 py-1.5 rounded-lg bg-primary/10 text-primary font-medium text-sm"
                    >
                      {cat.replace(/_/g, " ")}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.leaderboard && data.leaderboard.length > 0 && (
              <div className="rounded-2xl bg-white border border-gray-100 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                  <Award className="w-5 h-5 text-primary" />
                  <h2 className="font-semibold text-primary">Student Leaderboard</h2>
                </div>
                <div className="p-5 space-y-2">
                  {data.leaderboard.map((s, i) => (
                    <div
                      key={`${s.email}-${i}`}
                      className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
                          {i + 1}
                        </span>
                        <div>
                          <p className="font-medium text-gray-900 text-sm">{s.name}</p>
                          <p className="text-xs text-gray-500">{s.email}</p>
                        </div>
                      </div>
                      <span className="font-bold text-primary text-sm">{s.points} pts</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="rounded-2xl bg-white border border-gray-100 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
                <Users className="w-5 h-5 text-primary" />
                <h2 className="font-semibold text-primary">Top Queries</h2>
              </div>
              <div className="p-5">
                {data.top_queries.length > 0 ? (
                  <div className="space-y-2">
                    {data.top_queries.map((q, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-center py-2 px-3 rounded-lg bg-gray-50"
                      >
                        <span className="text-sm text-gray-700 truncate flex-1 mr-4">{q.query}</span>
                        <span className="text-sm font-medium text-primary">{q.count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">No queries logged yet.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </CopilotShell>
  );
}

export default function AnalyticsPage() {
  return (
    <RequireAuth roles={["admin", "super_admin"]}>
      <AnalyticsInner />
    </RequireAuth>
  );
}
