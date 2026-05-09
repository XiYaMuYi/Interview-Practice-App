"use client";

import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import EmptyState from "@/components/EmptyState";
import Pagination from "@/components/Pagination";
import SourceBadge from "@/components/SourceBadge";

// ─── Types ───────────────────────────────────────────────────────────

interface StudyStats {
  total_sessions: number;
  total_reviews: number;
  total_practice: number;
  average_score: number | null;
  questions_mastered: number;
  questions_pending: number;
}

interface StudyRecord {
  id: string;
  question_id: string;
  question_title: string;
  study_type: string;
  ai_score: number | null;
  mastery_level: number | null;
  source_type: string | null;
  created_at: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────

function formatTime(raw: string) {
  const d = new Date(raw);
  return d.toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function scoreColor(score: number) {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-yellow-600";
  return "text-red-600";
}

function masteryLabel(level: number | null) {
  if (level == null) return "未评级";
  const map: Record<number, string> = {
    0: "陌生", 1: "了解", 2: "熟悉", 3: "掌握", 4: "精通",
  };
  return map[level] || `${level}`;
}

function masteryColor(level: number | null) {
  if (level == null) return "bg-gray-100 text-gray-600";
  const map: Record<number, string> = {
    0: "bg-red-100 text-red-700", 1: "bg-orange-100 text-orange-700",
    2: "bg-yellow-100 text-yellow-700", 3: "bg-green-100 text-green-700",
    4: "bg-blue-100 text-blue-700",
  };
  return map[level] || "bg-gray-100 text-gray-600";
}

function studyTypeLabel(type: string) {
  const map: Record<string, string> = { practice: "练习", review: "复习" };
  return map[type] || type;
}

// ─── Page ────────────────────────────────────────────────────────────

export default function StatsPage() {
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [records, setRecords] = useState<StudyRecord[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  // Source breakdown
  const [sourceBreakdown, setSourceBreakdown] = useState<Record<string, number> | null>(null);
  const [loadingSource, setLoadingSource] = useState(false);

  const loadSourceBreakdown = useCallback(async () => {
    setLoadingSource(true);
    try {
      const res = await axios.get("/api/v1/study/stats/by-source");
      if (res.data && typeof res.data === "object") {
        setSourceBreakdown(res.data);
      }
    } catch {
      // endpoint may not exist — leave null
    } finally {
      setLoadingSource(false);
    }
  }, []);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [statsRes, recordsRes] = await Promise.allSettled([
          axios.get<StudyStats>("/api/v1/study/stats"),
          axios.get<{ items: StudyRecord[]; total?: number }>("/api/v1/study/records", {
            params: { page, page_size: limit },
          }),
        ]);

        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (recordsRes.status === "fulfilled") {
          setRecords(recordsRes.value.data.items);
          setTotalRecords(recordsRes.value.data.total ?? recordsRes.value.data.items.length);
        }
        if (statsRes.status === "rejected" && recordsRes.status === "rejected") {
          setError("获取数据失败，请确保后端服务正在运行");
        }
      } catch {
        setError("获取数据失败");
      } finally {
        setLoading(false);
      }
    }
    loadData();
    loadSourceBreakdown();
  }, [page, limit, loadSourceBreakdown]);

  if (loading) return <div className="max-w-5xl mx-auto px-4 py-12 text-center text-gray-500">加载中...</div>;
  if (error) return <div className="max-w-5xl mx-auto px-4 py-12 text-center text-red-500">{error}</div>;

  const s = stats;
  const practiceRatio = s && (s.total_practice + s.total_reviews > 0)
    ? Math.round((s.total_practice / (s.total_practice + s.total_reviews)) * 100)
    : 0;
  const masteryRate = s && (s.questions_mastered + s.questions_pending > 0)
    ? Math.round((s.questions_mastered / (s.questions_mastered + s.questions_pending)) * 100)
    : 0;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">学习统计</h1>

      {/* Summary cards */}
      {s && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {[
              { label: "总练习次数", value: s.total_practice, icon: "📝", bg: "bg-blue-50", border: "border-blue-200" },
              { label: "总复习次数", value: s.total_reviews, icon: "🔄", bg: "bg-green-50", border: "border-green-200" },
              { label: "总学习次数", value: s.total_sessions, icon: "📚", bg: "bg-indigo-50", border: "border-indigo-200" },
              {
                label: "平均分数",
                value: s.average_score != null ? s.average_score.toFixed(1) : "—",
                icon: "📊",
                bg: "bg-purple-50",
                border: "border-purple-200",
              },
              { label: "已掌握题目", value: s.questions_mastered, icon: "✅", bg: "bg-emerald-50", border: "border-emerald-200" },
              { label: "待复习题目", value: s.questions_pending, icon: "⏳", bg: "bg-amber-50", border: "border-amber-200" },
            ].map(({ label, value, icon, bg, border }) => (
              <div key={label} className={`${bg} ${border} border rounded-lg p-5`}>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-2xl">{icon}</span>
                  <span className="text-sm font-medium text-gray-600">{label}</span>
                </div>
                <div className="text-3xl font-bold text-gray-900">{value}</div>
              </div>
            ))}
          </div>

          {/* Progress bars */}
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">学习概览</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">练习 / 复习比例</span>
                  <span className="font-medium">{practiceRatio}% 练习</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div className="bg-blue-500 h-3 rounded-full transition-all" style={{ width: `${practiceRatio}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">掌握率</span>
                  <span className="font-medium">{masteryRate}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div className="bg-green-500 h-3 rounded-full transition-all" style={{ width: `${masteryRate}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Source dimension breakdown */}
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">题目来源分布</h3>
            {loadingSource ? (
              <p className="text-gray-500 text-sm">加载中...</p>
            ) : sourceBreakdown ? (
              <div className="flex flex-wrap gap-3">
                {Object.entries(sourceBreakdown).map(([source, count]) => (
                  <div key={source} className="flex items-center gap-2 bg-gray-50 rounded-lg px-4 py-3">
                    <SourceBadge source={source} />
                    <span className="text-lg font-bold text-gray-900">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">来源维度统计暂未开放</p>
            )}
          </div>
        </>
      )}

      {/* Recent records timeline */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">最近学习记录</h3>
        {records.length === 0 ? (
          <EmptyState
            title="暂无学习记录"
            description="开始练习或复习后，这里会显示你的学习记录"
          />
        ) : (
          <>
            <div className="space-y-3">
              {records.map((r, i) => (
                <div key={r.id} className="flex items-start gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center pt-1">
                    <div className={`w-3 h-3 rounded-full ${r.study_type === "practice" ? "bg-blue-500" : "bg-green-500"}`} />
                    {i < records.length - 1 && <div className="w-0.5 h-8 bg-gray-200 mt-1" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-900 truncate">{r.question_title || "无标题"}</span>
                      {r.source_type && <SourceBadge source={r.source_type} />}
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        r.study_type === "practice" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
                      }`}>
                        {studyTypeLabel(r.study_type)}
                      </span>
                      {r.ai_score != null && (
                        <span className={`text-sm font-bold ${scoreColor(r.ai_score)}`}>{r.ai_score} 分</span>
                      )}
                      {r.mastery_level != null && (
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${masteryColor(r.mastery_level)}`}>
                          {masteryLabel(r.mastery_level)}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 mt-1">{formatTime(r.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>

            <Pagination
              currentPage={page}
              pageSize={limit}
              total={totalRecords}
              onPageChange={setPage}
              onPageSizeChange={(s) => { setLimit(s); setPage(1); }}
            />
          </>
        )}
      </div>
    </div>
  );
}
