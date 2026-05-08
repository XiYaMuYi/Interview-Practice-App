"use client";

import { useEffect, useState } from "react";
import axios from "axios";

interface Question {
  id: number;
  title: string;
  content: string;
  difficulty: string;
  category: string | null;
  tags: string[];
  created_at: string;
}

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchQuestions() {
      try {
        const res = await axios.get("/api/v1/questions/");
        setQuestions(res.data);
      } catch {
        setError("获取题目失败，请确保后端服务正在运行");
      } finally {
        setLoading(false);
      }
    }
    fetchQuestions();
  }, []);

  const difficultyColor = (diff: string) => {
    switch (diff) {
      case "easy":
        return "bg-green-100 text-green-800";
      case "medium":
        return "bg-yellow-100 text-yellow-800";
      case "hard":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

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
      <h1 className="text-3xl font-bold text-gray-900 mb-8">题目列表</h1>

      {questions.length === 0 ? (
        <p className="text-gray-500">暂无题目，请先导入或添加题目。</p>
      ) : (
        <div className="grid gap-4">
          {questions.map((q) => (
            <div
              key={q.id}
              className="bg-white rounded-lg shadow-sm border p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-semibold text-gray-900 truncate">
                    {q.title || "无标题"}
                  </h2>
                  <p className="text-gray-600 mt-1 line-clamp-2">
                    {q.content}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  {q.difficulty && (
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${difficultyColor(q.difficulty)}`}
                    >
                      {q.difficulty}
                    </span>
                  )}
                  {q.category && (
                    <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800">
                      {q.category}
                    </span>
                  )}
                </div>
              </div>
              {q.tags && q.tags.length > 0 && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {q.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
