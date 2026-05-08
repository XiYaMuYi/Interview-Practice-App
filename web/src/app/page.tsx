"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import axios from "axios";

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
}

interface ListResponse {
  total: number;
  offset: number;
  limit: number;
  items: Question[];
}

// ─── Helpers ─────────────────────────────────────────────────────────

const difficultyText = (level: number | null) => {
  if (level == null) return "未定级";
  const map: Record<number, string> = { 1: "入门", 2: "简单", 3: "中等", 4: "困难", 5: "专家" };
  return map[level] || `${level}`;
};

const difficultyColor = (level: number | null) => {
  if (level == null) return "bg-gray-100 text-gray-600";
  const map: Record<number, string> = {
    1: "bg-green-100 text-green-700", 2: "bg-lime-100 text-lime-700",
    3: "bg-yellow-100 text-yellow-700", 4: "bg-orange-100 text-orange-700",
    5: "bg-red-100 text-red-700",
  };
  return map[level] || "bg-gray-100 text-gray-600";
};

// ─── Page ────────────────────────────────────────────────────────────

export default function HomePage() {
  const [stats, setStats] = useState<StudyStats | null>(null);
  const [recentQuestions, setRecentQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, questionsRes] = await Promise.allSettled([
          axios.get<StudyStats>("/api/v1/study/stats"),
          axios.get<ListResponse>("/api/v1/questions/", { params: { offset: 0, limit: 3 } }),
        ]);

        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (questionsRes.status === "fulfilled") setRecentQuestions(questionsRes.value.data.items);
      } catch {
        // silently ignore — sections will show fallback
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const features = [
    {
      title: "导入题目",
      description: "从文本或文件批量导入面试题目",
      href: "/import",
      icon: "📥",
      accent: "border-blue-200 hover:border-blue-400 hover:bg-blue-50",
    },
    {
      title: "浏览题目",
      description: "搜索、筛选和浏览面试题目库",
      href: "/questions",
      icon: "📋",
      accent: "border-purple-200 hover:border-purple-400 hover:bg-purple-50",
    },
    {
      title: "学习练习",
      description: "AI 评分 + 讲解，高效掌握要点",
      href: "/study",
      icon: "🎯",
      accent: "border-green-200 hover:border-green-400 hover:bg-green-50",
    },
    {
      title: "模拟面试",
      description: "沉浸式 AI 面试体验，追问到深入",
      href: "/interview",
      icon: "🎙️",
      accent: "border-amber-200 hover:border-amber-400 hover:bg-amber-50",
    },
    {
      title: "学习统计",
      description: "数据面板追踪练习进度和表现",
      href: "/stats",
      icon: "📊",
      accent: "border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50",
    },
  ];

  const quickStats = stats
    ? [
        { label: "总练习次数", value: stats.total_practice, color: "text-blue-600" },
        { label: "平均分数", value: stats.average_score != null ? stats.average_score.toFixed(1) : "—", color: "text-purple-600" },
        { label: "已掌握题目", value: stats.questions_mastered, color: "text-green-600" },
        { label: "待复习题目", value: stats.questions_pending, color: "text-amber-600" },
      ]
    : [];

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
      {!loading && quickStats.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {quickStats.map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl shadow-sm border p-5 text-center">
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-sm text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Feature Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
        {features.map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className={`bg-white rounded-xl shadow-sm border p-6 hover:shadow-md transition-all group ${f.accent}`}
          >
            <div className="text-4xl mb-4">{f.icon}</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
              {f.title}
            </h3>
            <p className="text-gray-600">{f.description}</p>
          </Link>
        ))}
      </div>

      {/* Recent Questions */}
      {!loading && recentQuestions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">最近导入</h2>
            <Link href="/questions" className="text-sm text-blue-600 hover:text-blue-800 transition-colors">
              查看全部 &rarr;
            </Link>
          </div>
          <div className="space-y-3">
            {recentQuestions.map((q) => (
              <Link
                key={q.id}
                href={`/questions/${q.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors group"
              >
                <span className="font-medium text-gray-900 group-hover:text-blue-600 transition-colors truncate">
                  {q.title || "无标题"}
                </span>
                <div className="flex gap-2 shrink-0 ml-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${difficultyColor(q.difficulty_level)}`}>
                    {difficultyText(q.difficulty_level)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Empty state when no data */}
      {!loading && recentQuestions.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          <svg className="mx-auto h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          <p className="text-lg font-medium">还没有导入题目</p>
          <Link href="/import" className="text-blue-600 hover:text-blue-800 mt-2 inline-block">
            开始导入 &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
