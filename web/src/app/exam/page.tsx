"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ExamSetupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [duration, setDuration] = useState(60);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState("");
  const [source, setSource] = useState("");

  const durationOptions = [
    { label: "30分钟", value: 30 },
    { label: "60分钟", value: 60 },
    { label: "90分钟", value: 90 },
    { label: "120分钟", value: 120 },
  ];

  const countOptions = [10, 20, 30, 50];

  const difficultyOptions = [
    { label: "不限", value: "" },
    { label: "简单", value: "easy" },
    { label: "中等", value: "medium" },
    { label: "困难", value: "hard" },
  ];

  const sourceOptions = [
    { label: "不限", value: "" },
    { label: "简历生成", value: "resume" },
    { label: "手动导入", value: "manual" },
    { label: "AI生成", value: "ai_generated" },
  ];

  const handleStartExam = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(`${API_BASE}/api/v1/exams/sessions`, {
        duration_minutes: duration,
        question_count: questionCount,
        difficulty_filter: difficulty || undefined,
        source_filter: source || undefined,
      });
      router.push(`/exam/session/${res.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "创建考试失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">📝 模拟考试</h1>
          <p className="text-gray-500 mb-8">自定义你的考试，检验学习成果</p>

          <div className="space-y-8">
            {/* Duration */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">考试时长</label>
              <div className="grid grid-cols-4 gap-3">
                {durationOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setDuration(opt.value)}
                    className={`py-3 px-4 rounded-lg border-2 text-center font-medium transition-all ${
                      duration === opt.value
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300 text-gray-600"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Count */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">题目数量</label>
              <div className="grid grid-cols-4 gap-3">
                {countOptions.map((count) => (
                  <button
                    key={count}
                    onClick={() => setQuestionCount(count)}
                    className={`py-3 px-4 rounded-lg border-2 text-center font-medium transition-all ${
                      questionCount === count
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300 text-gray-600"
                    }`}
                  >
                    {count}题
                  </button>
                ))}
              </div>
            </div>

            {/* Difficulty */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">难度筛选</label>
              <div className="grid grid-cols-4 gap-3">
                {difficultyOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setDifficulty(opt.value)}
                    className={`py-3 px-4 rounded-lg border-2 text-center font-medium transition-all ${
                      difficulty === opt.value
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300 text-gray-600"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Source */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">题目来源</label>
              <div className="grid grid-cols-4 gap-3">
                {sourceOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setSource(opt.value)}
                    className={`py-3 px-4 rounded-lg border-2 text-center font-medium transition-all ${
                      source === opt.value
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300 text-gray-600"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg">{error}</div>
            )}

            {/* Start Button */}
            <button
              onClick={handleStartExam}
              disabled={loading}
              className="w-full py-4 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "准备中..." : "开始考试"}
            </button>

            {/* Exam Rules */}
            <div className="border-t pt-6 mt-8">
              <h3 className="font-medium text-gray-700 mb-3">📋 考试说明</h3>
              <ul className="text-sm text-gray-500 space-y-2">
                <li>• 考试期间可以自由切换题目</li>
                <li>• 提交后自动批改，AI评分</li>
                <li>• 每题满分100分，总分按平均分计算</li>
                <li>• 建议先回答所有题目再提交</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
