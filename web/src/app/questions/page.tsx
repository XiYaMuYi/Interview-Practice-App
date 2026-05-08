"use client";

import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import QuestionCard from "@/components/QuestionCard";

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

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // filters
  const [domainFilter, setDomainFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { offset: 0, limit: 200 };
      if (domainFilter) params.domain_type = domainFilter;
      if (difficultyFilter) params.difficulty_level = parseInt(difficultyFilter, 10);

      const res = await axios.get<ListResponse>("/api/v1/questions/", { params });
      setQuestions(res.data.items);
      setTotal(res.data.total);
    } catch {
      setError("获取题目失败，请确保后端服务正在运行");
    } finally {
      setLoading(false);
    }
  }, [domainFilter, difficultyFilter]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const domains = [
    "RAG", "Backend", "Frontend", "Database", "DevOps", "Algorithm", "ML",
  ];

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-gray-500">
        加载中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-red-500">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          题目列表
          <span className="ml-3 text-lg font-normal text-gray-500">
            共 {total} 道
          </span>
        </h1>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border p-4 mb-6 flex gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">领域:</label>
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="">全部</option>
            {domains.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">难度:</label>
          <select
            value={difficultyFilter}
            onChange={(e) => setDifficultyFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
          >
            <option value="">全部</option>
            <option value="1">1 - 入门</option>
            <option value="2">2 - 简单</option>
            <option value="3">3 - 中等</option>
            <option value="4">4 - 困难</option>
            <option value="5">5 - 专家</option>
          </select>
        </div>
        {(domainFilter || difficultyFilter) && (
          <button
            onClick={() => {
              setDomainFilter("");
              setDifficultyFilter("");
            }}
            className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {questions.length === 0 ? (
        <p className="text-gray-500">暂无题目，请先导入或添加题目。</p>
      ) : (
        <div className="grid gap-4">
          {questions.map((q) => (
            <QuestionCard key={q.id} question={q} />
          ))}
        </div>
      )}
    </div>
  );
}
