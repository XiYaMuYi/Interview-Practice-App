"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import axios from "axios";
import ErrorState from "@/components/ErrorState";
import LoadingState from "@/components/LoadingState";
import EmptyState from "@/components/EmptyState";
import TaskStatusBadge from "@/components/TaskStatusBadge";
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

interface Question {
  id: string;
  title: string;
  question_type: string | null;
  domain_type: string | null;
  difficulty_level: number | null;
  source_type?: string;
}

interface ResumeSummary {
  name?: string;
  title?: string;
  top_skills?: string[];
}

interface ResumeItem {
  id: string;
  file_name: string;
  source_type: string;
  parse_status: string;
  structured_summary: ResumeSummary | null;
  created_at: string;
}

interface ListResponse {
  items: Question[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────

const difficultyColor = (level: number | null) => {
  if (level == null) return "bg-gray-100 text-gray-600";
  const map: Record<number, string> = {
    1: "bg-green-100 text-green-700", 2: "bg-lime-100 text-lime-700",
    3: "bg-yellow-100 text-yellow-700", 4: "bg-orange-100 text-orange-700",
    5: "bg-red-100 text-red-700",
  };
  return map[level] || "bg-gray-100 text-gray-600";
};

const difficultyText = (level: number | null) => {
  if (level == null) return "未定级";
  const map: Record<number, string> = { 1: "入门", 2: "简单", 3: "中等", 4: "困难", 5: "专家" };
  return map[level] || `${level}`;
};

const formatDate = (iso: string) => {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

// ─── Page ────────────────────────────────────────────────────────────

export default function HomePage() {
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [recentQuestions, setRecentQuestions] = useState<Question[]>([]);
  const [recentResumes, setRecentResumes] = useState<ResumeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, questionsRes, resumesRes] = await Promise.allSettled([
        axios.get<StudyStats>("/api/v1/study/stats"),
        axios.get<ListResponse>("/api/v1/questions", { params: { page: 1, page_size: 5 } }),
        axios.get<{ items: ResumeItem[] }>("/api/v1/resumes", { params: { page: 1, page_size: 3 } }),
      ]);

      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (questionsRes.status === "fulfilled") setRecentQuestions(questionsRes.value.data.items);
      if (resumesRes.status === "fulfilled") setRecentResumes(resumesRes.value.data.items);
    } catch {
      setError("加载概览数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  // ── Feature cards ─────────────────────────────────────────────────

  const features = [
    {
      title: "简历驱动面试",
      description: "上传简历，AI 自动提取技术栈并生成针对性面试题",
      href: "/import?tab=resume",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      ),
      accent: "border-rose-300 bg-gradient-to-br from-rose-50 to-white hover:border-rose-400 hover:shadow-md",
      priority: true,
    },
    {
      title: "导入题目",
      description: "从文本或文件批量导入面试题目",
      href: "/import",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      ),
      accent: "border-blue-200 hover:border-blue-400 hover:bg-blue-50",
    },
    {
      title: "浏览题目",
      description: "搜索、筛选和浏览面试题目库",
      href: "/questions",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      ),
      accent: "border-purple-200 hover:border-purple-400 hover:bg-purple-50",
    },
    {
      title: "学习练习",
      description: "AI 评分 + 讲解，高效掌握要点",
      href: "/study",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
        </svg>
      ),
      accent: "border-green-200 hover:border-green-400 hover:bg-green-50",
    },
    {
      title: "模拟面试",
      description: "沉浸式 AI 面试体验，追问到深入",
      href: "/interview",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
        </svg>
      ),
      accent: "border-amber-200 hover:border-amber-400 hover:bg-amber-50",
    },
    {
      title: "学习统计",
      description: "数据面板追踪练习进度和表现",
      href: "/stats",
      icon: (
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      ),
      accent: "border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50",
    },
  ];

  // ── Quick stats ───────────────────────────────────────────────────

  const quickStats = stats
    ? [
        { label: "总练习次数", value: stats.total_practice, color: "text-blue-600" },
        { label: "平均分数", value: stats.average_score != null ? stats.average_score.toFixed(1) : "—", color: "text-purple-600" },
        { label: "已掌握", value: stats.questions_mastered, color: "text-green-600" },
        { label: "待复习", value: stats.questions_pending, color: "text-amber-600" },
      ]
    : [];

  // ── Loading state ─────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <div className="h-10 w-48 bg-gray-200 rounded animate-pulse mx-auto mb-4" />
          <div className="h-5 w-96 bg-gray-100 rounded animate-pulse mx-auto" />
        </div>
        <LoadingState variant="skeleton" count={3} />
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────────

  if (error && quickStats.length === 0 && recentQuestions.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">面试练习平台</h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            导入题目、分类管理、AI 模拟面试，帮助你系统地准备技术面试
          </p>
        </div>
        <ErrorState
          message={error}
          onRetry={loadOverview}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          面试练习平台
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          导入题目、分类管理、AI 模拟面试，帮助你系统地准备技术面试
        </p>
      </div>

      {/* Quick Stats */}
      {quickStats.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {quickStats.map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl shadow-sm border p-5 text-center">
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-sm text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Feature Cards — priority card first */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
        {features.map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className={`rounded-xl shadow-sm border p-6 transition-all group ${f.accent} ${
              f.priority ? "sm:col-span-2 lg:col-span-1 lg:row-span-2 flex flex-col justify-center" : ""
            }`}
          >
            <div className={`mb-4 ${f.priority ? "text-rose-600" : "text-gray-700"}`}>{f.icon}</div>
            <h3 className={`font-semibold group-hover:text-blue-600 transition-colors ${f.priority ? "text-2xl mb-3" : "text-xl mb-2"}`}>
              {f.title}
            </h3>
            <p className={f.priority ? "text-gray-600 text-base" : "text-gray-600"}>{f.description}</p>
          </Link>
        ))}
      </div>

      {/* Two-column: Recent resumes + Recent questions */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Resumes */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">最近简历</h2>
            <Link href="/import" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              管理 &rarr;
            </Link>
          </div>
          {recentResumes.length === 0 ? (
            <EmptyState
              title="暂无简历"
              description="上传简历以启动简历驱动面试"
              actionLabel="上传简历"
              actionHref="/import"
            />
          ) : (
            <ul className="space-y-3">
              {recentResumes.map((r) => (
                <li key={r.id} className="flex items-start justify-between gap-3 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <SourceBadge source={r.source_type} />
                      <TaskStatusBadge status={r.parse_status} />
                    </div>
                    <p className="text-sm font-medium text-gray-900 truncate">{r.file_name}</p>
                    {r.structured_summary?.title && (
                      <p className="text-xs text-gray-500 mt-0.5">{r.structured_summary.title}</p>
                    )}
                    {r.structured_summary?.top_skills && r.structured_summary.top_skills.length > 0 && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {r.structured_summary.top_skills.slice(0, 5).join("、")}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-0.5">{formatDate(r.created_at)}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Link
                      href="/study"
                      className="px-3 py-1 text-xs text-blue-600 border border-blue-300 rounded hover:bg-blue-50 transition-colors"
                    >
                      开始面试
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent Questions */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">最近导入</h2>
            <Link href="/questions" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              查看全部 &rarr;
            </Link>
          </div>
          {recentQuestions.length === 0 ? (
            <EmptyState
              title="还没有导入题目"
              description="从文本、文件或简历开始导入"
              actionLabel="开始导入"
              actionHref="/import"
            />
          ) : (
            <ul className="space-y-3">
              {recentQuestions.map((q) => (
                <li key={q.id}>
                  <Link
                    href={`/questions/${q.id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors group"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-medium text-gray-900 group-hover:text-blue-600 transition-colors truncate block">
                        {q.title || "无标题"}
                      </span>
                      {q.source_type && (
                        <span className="mt-1">
                          <SourceBadge source={q.source_type} />
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0 ml-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${difficultyColor(q.difficulty_level)}`}>
                        {difficultyText(q.difficulty_level)}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Error banner if partial load failed */}
      {error && (quickStats.length > 0 || recentQuestions.length > 0 || recentResumes.length > 0) && (
        <div className="mt-6 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700 flex items-center justify-between">
          <span>{error}，部分数据可能未加载</span>
          <button onClick={loadOverview} className="text-yellow-800 underline ml-4">
            重试
          </button>
        </div>
      )}
    </div>
  );
}
